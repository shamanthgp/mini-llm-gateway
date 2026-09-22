from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_heartbeat_endpoint():
    payload = {
        "worker_name": "test-worker",
        "host": "localhost",
        "port": 9999,
        "status": "ready",
        "active_requests": 0,
        "model_name": "mock-model",
        "uptime": 100.0
    }
    response = client.post("/worker/heartbeat", json=payload)
    assert response.status_code == 200
