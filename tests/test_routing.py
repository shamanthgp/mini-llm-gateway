from fastapi.testclient import TestClient
from app.main import app
from app.registry import workers
import pytest

client = TestClient(app)

@pytest.fixture(autouse=True)
def reset_registry():
    workers.clear()

def test_no_workers_available():
    payload = {"model": "dummy", "messages": [{"role": "user", "content": "hi"}]}
    response = client.post("/v1/chat/completions", json=payload)
    assert response.status_code == 503
