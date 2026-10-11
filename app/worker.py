import sys
import time
import socket
from fastapi import FastAPI, Response
from fastapi.responses import StreamingResponse
import httpx
import asyncio
import uuid
from app.schemas import ChatCompletionRequest
from app.config import settings
from app.services.mock_inference import MockInferenceEngine
from app.services.ollama_inference import OllamaInferenceEngine
from app.services.api_inference import ApiInferenceEngine

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(send_heartbeat())
    yield
    task.cancel()

app = FastAPI(title="Mini LLM Gateway Worker", lifespan=lifespan)

WORKER_NAME = f"worker-{uuid.uuid4().hex[:6]}"
active_requests = 0
start_time = time.time()

mock_engine = MockInferenceEngine(WORKER_NAME)
ollama_engine = OllamaInferenceEngine(WORKER_NAME)
api_engine = ApiInferenceEngine(WORKER_NAME)
@app.post("/generate")
async def generate(request: ChatCompletionRequest, response: Response):
    global active_requests
    active_requests += 1
    try:
        if request.model == "gpt-3.5-turbo":
            result = await mock_engine.generate(request)
        elif request.model.startswith("ollama-"):
            request.model = request.model.replace("ollama-", "")
            result = await ollama_engine.generate(request)
        else:
            result = await api_engine.generate(request)
            
        response.headers["X-Served-By"] = WORKER_NAME
            
        if hasattr(result, "__aiter__"):  # It's an AsyncGenerator
            async def wrap_stream():
                global active_requests
                try:
                    async for chunk in result:
                        yield chunk
                finally:
                    active_requests -= 1
            return StreamingResponse(wrap_stream(), media_type="text/event-stream", headers={"X-Served-By": WORKER_NAME})
            
        active_requests -= 1
        
        # FastAPI handles serializing dict or BaseModel
        return result
    except Exception:
        active_requests -= 1
        raise

async def send_heartbeat():
    while True:
        try:
            async with httpx.AsyncClient() as client:
                host = settings.worker_host if settings.worker_host != "0.0.0.0" else socket.gethostname()
                payload = {
                    "worker_name": WORKER_NAME,
                    "host": host,
                    "port": settings.worker_port,
                    "status": "ready",
                    "active_requests": active_requests,
                    "model_name": "dynamic",
                    "uptime": time.time() - start_time
                }
                headers = {"X-Worker-Secret": settings.worker_shared_secret}
                await client.post(f"{settings.worker_gateway_url}/worker/heartbeat", json=payload, headers=headers, timeout=5.0)
                # Removed print statement to avoid spamming the terminal logs
        except Exception as e:
            print(f"[{WORKER_NAME}] Failed to send heartbeat to {settings.worker_gateway_url}: {e}")
            
        await asyncio.sleep(5)



if __name__ == "__main__":
    import uvicorn
    
    # Simple CLI override
    if "--port" in sys.argv:
        idx = sys.argv.index("--port")
        settings.worker_port = int(sys.argv[idx + 1])
        
    uvicorn.run(app, host=settings.worker_host, port=settings.worker_port, log_level="info")
