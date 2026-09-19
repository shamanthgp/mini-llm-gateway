import time
import uuid
import httpx
import json
from fastapi import HTTPException
from typing import AsyncGenerator, Union
from app.services.inference import InferenceEngine
from app.schemas import ChatCompletionRequest, ChatCompletionResponse, ChatCompletionChoice, ChatMessage
from app.config import settings

class ApiInferenceEngine(InferenceEngine):
    def __init__(self, worker_name: str):
        self.worker_name = worker_name
        self.api_url = settings.api_base_url.rstrip("/") + "/chat/completions"
        self.api_key = settings.api_key
        self.model_name = "cloud-api-proxy"

    async def generate(self, request: ChatCompletionRequest) -> Union[ChatCompletionResponse, AsyncGenerator[str, None]]:
        payload = {
            "model": request.model,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
            "stream": request.stream
        }
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        if request.stream:
            async def stream_generator() -> AsyncGenerator[str, None]:
                async with httpx.AsyncClient() as client:
                    try:
                        async with client.stream("POST", self.api_url, json=payload, headers=headers, timeout=120.0) as response:
                            if response.status_code != 200:
                                await response.aread()
                                error_msg = f"API Error {response.status_code}: {response.text}"
                                error_json = json.dumps({"error": error_msg})
                                yield f"data: {error_json}\n\n"
                                yield "data: [DONE]\n\n"
                                return
                                
                            async for line in response.aiter_lines():
                                if line and line.startswith("data: "):
                                    yield f"{line}\n\n"
                    except Exception as e:
                        yield f"data: {{\"error\": \"API unreachable: {str(e)}\"}}\n\n"
                        yield "data: [DONE]\n\n"
            return stream_generator()
        else:
            async with httpx.AsyncClient() as client:
                try:
                    response = await client.post(self.api_url, json=payload, headers=headers, timeout=120.0)
                    response.raise_for_status()
                    data = response.json()
                    
                    if data.get("choices") and data["choices"][0].get("message"):
                        data["choices"][0]["message"]["content"] = f"[{self.worker_name} via API] " + data["choices"][0]["message"]["content"]
                    
                    return ChatCompletionResponse(**data)
                except httpx.HTTPStatusError as e:
                    raise HTTPException(status_code=e.response.status_code, detail=f"API Error: {e.response.text}")
                except httpx.RequestError as e:
                    raise HTTPException(status_code=502, detail=f"API unreachable: {str(e)}")
