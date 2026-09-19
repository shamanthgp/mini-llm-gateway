import asyncio
import time
import uuid
import random
import json
from typing import AsyncGenerator, Union
from app.services.inference import InferenceEngine
from app.schemas import ChatCompletionRequest, ChatCompletionResponse, ChatCompletionChoice, ChatMessage

class MockInferenceEngine(InferenceEngine):
    def __init__(self, worker_name: str):
        self.worker_name = worker_name
        self.model_name = "mock-llm-1.0"

    async def generate(self, request: ChatCompletionRequest) -> Union[ChatCompletionResponse, AsyncGenerator[str, None]]:
        tokens_to_gen = request.max_tokens or 50
        req_id = f"chatcmpl-{uuid.uuid4().hex}"
        
        if request.stream:
            async def stream_generator() -> AsyncGenerator[str, None]:
                response_text = f"Hello from {self.worker_name} [MOCK]! Streaming is now working beautifully across the network."
                words = response_text.split(" ")
                for word in words:
                    await asyncio.sleep(random.uniform(0.05, 0.2))
                    chunk = {
                        "id": req_id,
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": request.model,
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"content": word + " "},
                                "finish_reason": None
                            }
                        ]
                    }
                    yield f"data: {json.dumps(chunk)}\n\n"
                    
                await asyncio.sleep(0.1)
                chunk = {
                    "id": req_id,
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": request.model,
                    "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]
                }
                yield f"data: {json.dumps(chunk)}\n\n"
                yield "data: [DONE]\n\n"
                
            return stream_generator()
        else:
            sleep_time = (tokens_to_gen / 20.0) + random.uniform(0.1, 0.5)
            await asyncio.sleep(sleep_time)
            
            response_text = f"Hello from {self.worker_name} [MOCK]! Generated {tokens_to_gen} tokens."
            
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
                usage={"prompt_tokens": 10, "completion_tokens": tokens_to_gen, "total_tokens": 10 + tokens_to_gen}
            )
