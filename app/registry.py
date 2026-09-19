import time
from typing import Optional, Dict, Any, List

HEARTBEAT_TIMEOUT = 15.0

workers: Dict[str, Any] = {}

metrics = {
    "total_requests": 0,
    "successful_requests": 0,
    "failed_requests": 0,
    "total_latency_ms": 0.0
}

def update_worker_status(worker_name: str, host: str, port: int, status: str, active_requests: int, model_name: str, uptime: float):
    workers[worker_name] = {
        "host": host,
        "port": port,
        "status": status,
        "active_requests": active_requests,
        "model_name": model_name,
        "uptime": uptime,
        "last_heartbeat": time.time()
    }

def get_least_busy_worker() -> Optional[Dict[str, Any]]:
    current_time = time.time()
    active_workers = {}
    for name, data in workers.items():
        if current_time - data["last_heartbeat"] <= HEARTBEAT_TIMEOUT:
            if data["status"] == "ready":
                active_workers[name] = data

    if not active_workers:
        return None
    
    return min(active_workers.values(), key=lambda w: w["active_requests"])

def prune_stale_workers() -> List[str]:
    current_time = time.time()
    stale = [
        name for name, data in workers.items() 
        if current_time - data["last_heartbeat"] > HEARTBEAT_TIMEOUT and data["status"] != "OFFLINE"
    ]
    for name in stale:
        workers[name]["status"] = "OFFLINE"
    
    dead = [
        name for name, data in workers.items()
        if current_time - data["last_heartbeat"] > HEARTBEAT_TIMEOUT + 60.0
    ]
    for name in dead:
        del workers[name]
        
    return stale
    
def record_metrics(success: bool, latency_ms: float):
    metrics["total_requests"] += 1
    if success:
        metrics["successful_requests"] += 1
        metrics["total_latency_ms"] += latency_ms
    else:
        metrics["failed_requests"] += 1

def get_metrics() -> Dict[str, Any]:
    active = sum(w.get("active_requests", 0) for w in workers.values() if w["status"] == "ready")
    avg_latency = 0
    if metrics["successful_requests"] > 0:
        avg_latency = metrics["total_latency_ms"] / metrics["successful_requests"]
        
    return {
        "total_requests": metrics["total_requests"],
        "successful_requests": metrics["successful_requests"],
        "failed_requests": metrics["failed_requests"],
        "active_requests": active,
        "avg_latency_ms": avg_latency
    }
