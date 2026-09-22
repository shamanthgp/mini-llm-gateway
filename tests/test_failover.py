import pytest
import time
from app.registry import update_worker_status, prune_stale_workers, workers

@pytest.fixture(autouse=True)
def reset_registry():
    workers.clear()

def test_failover_pruning():
    update_worker_status("worker-1", "localhost", 8001, "ready", 0, "mock-model", 100.0)
    workers["worker-1"]["last_heartbeat"] = time.time() - 20.0 # Force stale (offline)
    prune_stale_workers()
    assert workers["worker-1"]["status"] == "OFFLINE"

def test_failover_dead_removal():
    update_worker_status("worker-1", "localhost", 8001, "ready", 0, "mock-model", 100.0)
    workers["worker-1"]["last_heartbeat"] = time.time() - 80.0 # Force dead (removed)
    prune_stale_workers()
    assert "worker-1" not in workers
