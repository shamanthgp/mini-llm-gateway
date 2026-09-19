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

    async def generate(self, request: ChatCompletionRequest) -> Union[ChatCompletionResponse, AsyncGenerator[str, None]]:
        prompt = ""
        for msg in request.messages:
            prompt += f"{msg.role}: {msg.content}\n"
            
        payload = {
            "model": request.model,
            "prompt": prompt,
            "stream": request.stream
        }
        
        req_id = f"chatcmpl-{uuid.uuid4().hex}"
        
        if request.stream:
            async def stream_generator() -> AsyncGenerator[str, None]:
                async with httpx.AsyncClient() as client:
                    async with client.stream("POST", f"{self.ollama_url}/api/generate", json=payload, timeout=120.0) as response:
                        response.raise_for_status()
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
                                                "delta": {"content": data.get("response", "")},
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
                                        
                                except Exception as e:
                                    pass
            return stream_generator()
        else:
            async with httpx.AsyncClient() as client:
                try:
                    response = await client.post(f"{self.ollama_url}/api/generate", json=payload, timeout=120.0)
                    response.raise_for_status()
                    data = response.json()
                except httpx.RequestError as e:
                    raise HTTPException(status_code=502, detail=f"Ollama is not running or unreachable at {self.ollama_url}: {str(e)}")
                    
            response_text = f"[{self.worker_name} via Ollama] " + data.get("response", "")
            
            return ChatCompletionResponse(
                id=req_id,
                created=int(time.time()),
                model=request.model,
                choices=[
                    ChatCompletionChoice(
                        index=0,
                        message=ChatMessage(role="assistant", content=response_text),
                        finish_reason="stop"
                    )
                ],
                usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
            )
