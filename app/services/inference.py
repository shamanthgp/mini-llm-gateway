from abc import ABC, abstractmethod
from typing import AsyncGenerator, Dict, Any, Union
from app.schemas import ChatCompletionRequest, ChatCompletionResponse

class InferenceEngine(ABC):
    @abstractmethod
    async def generate(self, request: ChatCompletionRequest) -> Union[ChatCompletionResponse, AsyncGenerator[str, None]]:
        """Generates a response for a chat completion request."""
        pass
