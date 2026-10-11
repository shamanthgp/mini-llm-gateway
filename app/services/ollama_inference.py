import time
import uuid
import httpx
import json
from fastapi import HTTPException
from typing import AsyncGenerator, Union
from app.services.inference import InferenceEngine
from app.schemas import ChatCompletionRequest, ChatCompletionResponse, ChatCompletionChoice, ChatMessage
from app.config import settings

class OllamaInferenceEngine(InferenceEngine):
    def __init__(self, worker_name: str):
        self.worker_name = worker_name
        self.ollama_url = settings.ollama_url
        self.model_name = "ollama-proxy"

    async def generate(self, request: ChatCompletionRequest) -> Union[dict, AsyncGenerator[str, None]]:
        options = {}
        if request.temperature is not None:
            options["temperature"] = request.temperature
        if request.max_tokens is not None:
            options["num_predict"] = request.max_tokens
            
        payload = {
            "model": request.model,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
            "stream": request.stream
        }
        if options:
            payload["options"] = options
            
        req_id = f"chatcmpl-{uuid.uuid4().hex}"
        
        if request.stream:
            async def stream_generator() -> AsyncGenerator[str, None]:
                async with httpx.AsyncClient() as client:
                    try:
                        async with client.stream("POST", f"{self.ollama_url}/api/chat", json=payload, timeout=120.0) as response:
                            if response.status_code != 200:
                                await response.aread()
                                error_json = json.dumps({"error": {"message": f"Ollama returned {response.status_code}: {response.text}", "type": "ollama_error"}})
                                yield f"data: {error_json}\n\n"
                                yield "data: [DONE]\n\n"
                                return
                                
                            async for line in response.aiter_lines():
                                if line:
                                    try:
                                        data = json.loads(line)
                                        chunk = {
                                            "id": req_id,
                                            "object": "chat.completion.chunk",
                                            "created": int(time.time()),
                                            "model": request.model,
                                            "choices": [
                                                {
                                                    "index": 0,
                                                    "delta": {"content": data.get("message", {}).get("content", "")},
                                                    "finish_reason": None
                                                }
                                            ]
                                        }
                                        yield f"data: {json.dumps(chunk)}\n\n"
                                        
                                        if data.get("done"):
                                            chunk["choices"][0]["delta"] = {}
                                            chunk["choices"][0]["finish_reason"] = "stop"
                                            yield f"data: {json.dumps(chunk)}\n\n"
                                            yield "data: [DONE]\n\n"
                                            
                                    except json.JSONDecodeError as e:
                                        print(f"JSON parse error from Ollama: {e}")
                    except Exception as e:
                        error_json = json.dumps({"error": {"message": f"Ollama unreachable: {str(e)}", "type": "ollama_error"}})
                        yield f"data: {error_json}\n\n"
                        yield "data: [DONE]\n\n"
            return stream_generator()
        else:
            async with httpx.AsyncClient() as client:
                try:
                    response = await client.post(f"{self.ollama_url}/api/chat", json=payload, timeout=120.0)
                    response.raise_for_status()
                    data = response.json()
                except httpx.HTTPStatusError as e:
                    raise HTTPException(status_code=e.response.status_code, detail=f"Ollama Error: {e.response.text}")
                except httpx.RequestError as e:
                    raise HTTPException(status_code=502, detail=f"Ollama is not running or unreachable at {self.ollama_url}: {str(e)}")
                    
            response_text = data.get("message", {}).get("content", "")
            
            return {
                "id": req_id,
                "created": int(time.time()),
                "model": request.model,
                "object": "chat.completion",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": response_text},
                        "finish_reason": "stop"
                    }
                ],
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
            }
