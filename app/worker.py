import argparse
import sys
import time
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
import httpx
import asyncio
import uuid
from app.schemas import ChatCompletionRequest, ChatCompletionResponse
from app.config import settings
from app.services.mock_inference import MockInferenceEngine
from app.services.ollama_inference import OllamaInferenceEngine
from app.services.api_inference import ApiInferenceEngine

app = FastAPI(title="Mini LLM Gateway Worker")

WORKER_NAME = f"worker-{uuid.uuid4().hex[:6]}"
active_requests = 0
start_time = time.time()

mock_engine = MockInferenceEngine(WORKER_NAME)
ollama_engine = OllamaInferenceEngine(WORKER_NAME)
api_engine = ApiInferenceEngine(WORKER_NAME)

@app.post("/generate")
async def generate(request: ChatCompletionRequest):
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
            
        if hasattr(result, "__aiter__"):  # It's an AsyncGenerator
            return StreamingResponse(result, media_type="text/event-stream")
        return result
    finally:
        active_requests -= 1

async def send_heartbeat():
    while True:
        try:
            async with httpx.AsyncClient() as client:
                payload = {
                    "worker_name": WORKER_NAME,
                    "host": settings.worker_host,
                    "port": settings.worker_port,
                    "status": "ready",
                    "active_requests": active_requests,
                    "model_name": "dynamic",
                    "uptime": time.time() - start_time
                }
                await client.post(f"{settings.worker_gateway_url}/worker/heartbeat", json=payload, timeout=5.0)
                # Removed print statement to avoid spamming the terminal logs
        except Exception as e:
            print(f"[{WORKER_NAME}] Failed to send heartbeat to {settings.worker_gateway_url}: {e}")
            
        await asyncio.sleep(5)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(send_heartbeat())

if __name__ == "__main__":
    import uvicorn
    
    # Simple CLI override
    if "--port" in sys.argv:
        idx = sys.argv.index("--port")
        settings.worker_port = int(sys.argv[idx + 1])
        
    uvicorn.run(app, host=settings.worker_host, port=settings.worker_port, log_level="info")
