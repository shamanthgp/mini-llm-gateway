import pytest
import json
from unittest.mock import patch
from app.services.mock_inference import MockInferenceEngine
from app.services.api_inference import ApiInferenceEngine
from app.schemas import ChatCompletionRequest, ChatMessage

@pytest.mark.asyncio
async def test_mock_inference():
    engine = MockInferenceEngine("test-worker")
    req = ChatCompletionRequest(model="dummy", messages=[ChatMessage(role="user", content="hi")], max_tokens=10)
    resp = await engine.generate(req)
    assert isinstance(resp, dict)
    assert "[MOCK]" not in resp["choices"][0]["message"]["content"]
    assert "test-worker" not in resp["choices"][0]["message"]["content"]

@pytest.mark.asyncio
async def test_api_inference_params_and_pass_through():
    engine = ApiInferenceEngine("test-worker")
    
    # Extra field 'tool_calls' and null content
    req_data = {
        "model": "gpt-4",
        "messages": [{"role": "assistant", "content": None, "tool_calls": [{"id": "1"}]}],
        "temperature": 0.5,
        "max_tokens": 200,
        "stream": False
    }
    req = ChatCompletionRequest(**req_data)
    
    class MockResponse:
        def __init__(self, json_data, status_code=200):
            self._json = json_data
            self.status_code = status_code
            
        def json(self):
            return self._json
            
        def raise_for_status(self):
            if self.status_code >= 400:
                import httpx
                request = httpx.Request("POST", "http://test")
                raise httpx.HTTPStatusError("Error", request=request, response=self)
    
    # Fake response with no prefix
    fake_resp = {
        "id": "123",
        "choices": [{"message": {"role": "assistant", "content": "hello"}}]
    }
    
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = MockResponse(fake_resp)
        resp = await engine.generate(req)
        
        # Assert parameters passed through
        call_kwargs = mock_post.call_args[1]
        payload = call_kwargs["json"]
        assert payload["temperature"] == 0.5
        assert payload["max_tokens"] == 200
        assert payload["messages"][0]["tool_calls"] == [{"id": "1"}]
        assert "content" not in payload["messages"][0]
        
        # Assert no prefix in response
        assert resp["choices"][0]["message"]["content"] == "hello"

@pytest.mark.asyncio
async def test_api_inference_sse_error_quotes():
    engine = ApiInferenceEngine("test-worker")
    req = ChatCompletionRequest(model="gpt-4", messages=[], stream=True)
    
    class MockStreamContextManager:
        async def __aenter__(self):
            class MockResponse:
                status_code = 500
                text = 'Error with "quotes"'
                async def aread(self): pass
            return MockResponse()
        async def __aexit__(self, exc_type, exc_val, exc_tb): pass
        
    with patch("httpx.AsyncClient.stream", return_value=MockStreamContextManager()):
        gen = await engine.generate(req)
        chunks = [c async for c in gen]
        
        # Parse the JSON from the SSE string: data: {...}\n\n
        data_str = chunks[0][6:-2]
        parsed = json.loads(data_str)
        assert parsed["error"]["message"] == 'API Error 500: Error with "quotes"'
        assert parsed["error"]["type"] == "api_error"
