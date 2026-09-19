import pytest
from app.services.mock_inference import MockInferenceEngine
from app.schemas import ChatCompletionRequest, ChatMessage

@pytest.mark.asyncio
async def test_mock_inference():
    engine = MockInferenceEngine("test-worker")
    req = ChatCompletionRequest(model="dummy", messages=[ChatMessage(role="user", content="hi")], max_tokens=10)
    resp = await engine.generate(req)
    assert "test-worker" in resp.choices[0].message.content
