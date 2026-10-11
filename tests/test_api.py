from fastapi.testclient import TestClient
from app.main import app
from app.config import settings

client = TestClient(app)

def test_heartbeat_without_secret_fails():
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
    assert response.status_code == 401

def test_heartbeat_with_secret_succeeds():
    payload = {
        "worker_name": "test-worker",
        "host": "localhost",
        "port": 9999,
        "status": "ready",
        "active_requests": 0,
        "model_name": "mock-model",
        "uptime": 100.0
    }
    headers = {"X-Worker-Secret": settings.worker_shared_secret}
    response = client.post("/worker/heartbeat", json=payload, headers=headers)
    assert response.status_code == 200

def test_client_auth_missing_or_wrong():
    # Set dummy API keys for test
    settings.gateway_api_keys = "key1,key2"
    
    response = client.get("/metrics")
    assert response.status_code == 401
    
    response = client.get("/metrics", headers={"Authorization": "Bearer wrong-key"})
    assert response.status_code == 401
    
    response = client.get("/metrics", headers={"Authorization": "Bearer key1"})
    assert response.status_code == 200
    
    # Restore empty setting
    settings.gateway_api_keys = ""
