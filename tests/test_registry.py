import pytest
from app.registry import update_worker_status, get_least_busy_worker, prune_stale_workers, workers

@pytest.fixture(autouse=True)
def reset_registry():
    workers.clear()

def test_add_worker():
    update_worker_status("worker-1", "localhost", 8001, "ready", 0)
    assert "worker-1" in workers

def test_get_least_busy_worker():
    update_worker_status("worker-1", "localhost", 8001, "ready", 5)
    update_worker_status("worker-2", "localhost", 8002, "ready", 2)
    assert get_least_busy_worker()["port"] == 8002
