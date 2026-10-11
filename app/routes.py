from fastapi import APIRouter, HTTPException, Depends, Header
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import httpx
import time
import hmac

from app.schemas import WorkerHeartbeat, ChatCompletionRequest
from app import registry
from app.config import settings
import json

router = APIRouter()

security = HTTPBearer(auto_error=False)

# Shared client
http_client = httpx.AsyncClient()

def verify_client_key(credentials: HTTPAuthorizationCredentials = Depends(security)):
    keys = [k.strip() for k in settings.gateway_api_keys.split(",") if k.strip()]
    if not keys:
        return
    if not credentials:
        raise HTTPException(status_code=401, detail="Missing authorization header")
    if credentials.credentials not in keys:
        raise HTTPException(status_code=401, detail="Invalid API key")

def verify_worker(x_worker_secret: str = Header(None)):
    if x_worker_secret is None:
        raise HTTPException(status_code=401, detail="Missing worker secret")
    if not hmac.compare_digest(x_worker_secret.encode(), settings.worker_shared_secret.encode()):
        raise HTTPException(status_code=401, detail="Invalid worker secret")

@router.get("/metrics", dependencies=[Depends(verify_client_key)])
async def get_metrics():
    return registry.get_metrics()

@router.get("/workers", dependencies=[Depends(verify_client_key)])
async def get_workers():
    return {"workers": registry.workers}

@router.post("/worker/heartbeat", dependencies=[Depends(verify_worker)])
async def worker_heartbeat(heartbeat: WorkerHeartbeat):
    allowed_hosts = [h.strip() for h in settings.worker_allowed_hosts.split(",") if h.strip()]
    if allowed_hosts and heartbeat.host not in allowed_hosts:
        raise HTTPException(status_code=403, detail="Worker host not allowed")
        
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

@router.post("/v1/chat/completions", dependencies=[Depends(verify_client_key)])
async def chat_completions(request: ChatCompletionRequest):
    start_time = time.time()
    tried_workers = set()
    last_error_msg = "No healthy workers available"
    last_status = 503
    
    for attempt in range(settings.max_retries + 1):
        worker_name = registry.get_least_busy_worker(exclude=tried_workers)
        
        if not worker_name:
            break
            
        tried_workers.add(worker_name)
        registry.acquire_worker(worker_name)
        worker_data = registry.workers[worker_name]
        worker_url = f"http://{worker_data['host']}:{worker_data['port']}/generate"
        
        try:
            req = http_client.build_request("POST", worker_url, json=request.model_dump(), timeout=120.0)
            response = await http_client.send(req, stream=request.stream)
            
            if response.status_code >= 500:
                registry.workers[worker_name]["status"] = "OFFLINE"
                registry.release_worker(worker_name)
                last_error_msg = f"Worker {worker_name} returned {response.status_code}"
                last_status = 502
                continue
            
            if response.status_code >= 400:
                registry.record_metrics(success=False, latency_ms=(time.time() - start_time) * 1000)
                registry.release_worker(worker_name)
                if request.stream:
                    await response.aread()
                try:
                    body = response.json()
                except Exception:
                    body = response.text
                raise HTTPException(status_code=response.status_code, detail=body)

            if request.stream:
                async def proxy_stream():
                    try:
                        async for chunk in response.aiter_raw():
                            yield chunk
                        registry.record_metrics(success=True, latency_ms=(time.time() - start_time) * 1000)
                    except Exception as e:
                        registry.record_metrics(success=False, latency_ms=0)
                        error_event = json.dumps({"error": {"message": str(e), "type": "stream_error"}})
                        yield f"data: {error_event}\n\n"
                        yield "data: [DONE]\n\n"
                    finally:
                        registry.release_worker(worker_name)
                        await response.aclose()
                        
                return StreamingResponse(proxy_stream(), media_type="text/event-stream")
            else:
                registry.record_metrics(success=True, latency_ms=(time.time() - start_time) * 1000)
                resp_json = response.json()
                registry.release_worker(worker_name)
                return resp_json

        except httpx.RequestError as e:
            registry.workers[worker_name]["status"] = "OFFLINE"
            registry.release_worker(worker_name)
            last_error_msg = f"Worker {worker_name} unreachable: {str(e)}"
            last_status = 502
            continue
            
    registry.record_metrics(success=False, latency_ms=0)
    raise HTTPException(status_code=last_status, detail=last_error_msg)
