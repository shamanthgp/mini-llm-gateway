from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import httpx
import time

from app.schemas import WorkerHeartbeat, ChatCompletionRequest, ChatCompletionResponse
from app import registry

router = APIRouter()

@router.get("/metrics")
async def get_metrics():
    return registry.get_metrics()

@router.get("/workers")
async def get_workers():
    return {"workers": registry.workers}

@router.post("/worker/heartbeat")
async def worker_heartbeat(heartbeat: WorkerHeartbeat):
    registry.update_worker_status(
        worker_name=heartbeat.worker_name,
        host=heartbeat.host,
        port=heartbeat.port,
        status=heartbeat.status,
        active_requests=heartbeat.active_requests,
        model_name=heartbeat.model_name,
        uptime=heartbeat.uptime
    )
    return {"status": "ok"}

@router.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    start_time = time.time()
    worker = registry.get_least_busy_worker()
    
    if not worker:
        registry.record_metrics(success=False, latency_ms=0)
        raise HTTPException(status_code=503, detail="No healthy workers available")
    
    worker["active_requests"] += 1
    worker_url = f"http://{worker['host']}:{worker['port']}/generate"
    
    client = httpx.AsyncClient()
    
    if request.stream:
        async def proxy_stream():
            try:
                async with client.stream("POST", worker_url, json=request.model_dump(), timeout=120.0) as response:
                    if response.status_code != 200:
                        registry.record_metrics(success=False, latency_ms=0)
                        yield f"data: {{\"error\": \"Worker returned {response.status_code}\"}}\n\n"
                        yield "data: [DONE]\n\n"
                        return
                        
                    async for chunk in response.aiter_raw():
                        yield chunk
                registry.record_metrics(success=True, latency_ms=(time.time() - start_time) * 1000)
            except Exception as e:
                registry.record_metrics(success=False, latency_ms=0)
                yield f"data: {{\"error\": \"{str(e)}\"}}\n\n"
                yield "data: [DONE]\n\n"
            finally:
                worker["active_requests"] = max(0, worker["active_requests"] - 1)
                await client.aclose()
                
        return StreamingResponse(proxy_stream(), media_type="text/event-stream")
    else:
        try:
            response = await client.post(worker_url, json=request.model_dump(), timeout=120.0)
            response.raise_for_status()
            registry.record_metrics(success=True, latency_ms=(time.time() - start_time) * 1000)
            return response.json()
        except httpx.RequestError as e:
            registry.record_metrics(success=False, latency_ms=(time.time() - start_time) * 1000)
            raise HTTPException(status_code=502, detail=f"Worker unreachable: {str(e)}")
        finally:
            worker["active_requests"] = max(0, worker["active_requests"] - 1)
            await client.aclose()
