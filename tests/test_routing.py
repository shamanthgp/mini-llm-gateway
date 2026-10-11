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

def test_heartbeat_preserves_inflight():
    from app.registry import update_worker_status, workers, get_least_busy_worker, acquire_worker, release_worker
    
    # First heartbeat
    update_worker_status("worker1", "localhost", 8001, "ready", 0, "dummy", 10.0)
    assert workers["worker1"]["inflight"] == 0
    
    acquire_worker("worker1")
    assert workers["worker1"]["inflight"] == 1
    
    # Second heartbeat should not reset inflight
    update_worker_status("worker1", "localhost", 8001, "ready", 0, "dummy", 20.0)
    assert workers["worker1"]["inflight"] == 1
    
    # Release
    release_worker("worker1")
    assert workers["worker1"]["inflight"] == 0

def test_routing_picks_lower_inflight():
    from app.registry import update_worker_status, get_least_busy_worker, acquire_worker
    
    update_worker_status("worker1", "localhost", 8001, "ready", 0, "dummy", 10.0)
    update_worker_status("worker2", "localhost", 8002, "ready", 0, "dummy", 10.0)
    
    acquire_worker("worker1")
    
    # worker1 has 1 inflight, worker2 has 0 inflight. It should pick worker2
    assert get_least_busy_worker() == "worker2"
from unittest.mock import patch
import httpx

def test_retry_on_worker_failure():
    from app.registry import update_worker_status, workers
    
    update_worker_status("worker1", "localhost", 8001, "ready", 0, "dummy", 10.0)
    update_worker_status("worker2", "localhost", 8002, "ready", 0, "dummy", 10.0)
    
    class MockResponse:
        def __init__(self, status_code, json_data):
            self.status_code = status_code
            self._json = json_data
            
        def json(self):
            return self._json
            
    # Mock send to fail on first call (worker1) and succeed on second (worker2)
    side_effect = [
        httpx.ConnectError("Connection refused"),
        MockResponse(200, {"choices": []})
    ]
    
    with patch("httpx.AsyncClient.send", side_effect=side_effect):
        response = client.post("/v1/chat/completions", json={"model": "dummy", "messages": []})
        
    assert response.status_code == 200
    assert workers["worker1"]["status"] == "OFFLINE"
    assert workers["worker2"]["status"] == "ready"

def test_retry_fails_all():
    from app.registry import update_worker_status, workers
    workers.clear()
    update_worker_status("worker1", "localhost", 8001, "ready", 0, "dummy", 10.0)
    
    with patch("httpx.AsyncClient.send", side_effect=httpx.ConnectError("Connection refused")):
        response = client.post("/v1/chat/completions", json={"model": "dummy", "messages": []})
        
    assert response.status_code == 502
    assert workers["worker1"]["status"] == "OFFLINE"

def test_no_retry_on_4xx():
    from app.registry import update_worker_status, workers, metrics
    workers.clear()
    
    initial_failed = metrics["failed_requests"]
    update_worker_status("worker1", "localhost", 8001, "ready", 0, "dummy", 10.0)
    update_worker_status("worker2", "localhost", 8002, "ready", 0, "dummy", 10.0)
    
    class MockResponse:
        def __init__(self, status_code, json_data):
            self.status_code = status_code
            self._json = json_data
            self.headers = {"content-type": "application/json"}
            
        def json(self):
            return self._json
            
        async def aread(self):
            pass
            
        async def aclose(self):
            pass
            
    with patch("httpx.AsyncClient.send", return_value=MockResponse(429, {"error": "Too Many Requests"})):
        response = client.post("/v1/chat/completions", json={"model": "dummy", "messages": []})
        
    assert response.status_code == 429
    # Should not mark OFFLINE for 429
    assert workers["worker1"]["status"] == "ready"
    assert metrics["failed_requests"] == initial_failed + 1
