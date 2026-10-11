# 📦 Release Notes — Commit `c531ad1`

**Repository:** [shamanthgp/mini-llm-gateway](https://github.com/shamanthgp/mini-llm-gateway)
**Branch:** `main`
**Date:** October 12, 2026
**Diff:** 20 files changed · **+550** additions · **-202** deletions

---

## Overview

This commit introduces **security hardening**, **request failover**, **accurate load tracking**, and **schema flexibility** to the Mini LLM Gateway. It also modernizes the worker lifecycle, simplifies the Docker setup, and adds comprehensive test coverage for the new behaviors.

---

## 🔐 1. Authentication & Authorization

### Client-Facing API Key Auth
- All client endpoints (`/v1/chat/completions`, `/workers`, `/metrics`) now require a **Bearer token** when `GATEWAY_API_KEYS` is configured.
- Multiple comma-separated keys are supported. If the env var is empty/unset, auth is disabled (open access).
- Implementation: `verify_client_key` dependency in [`app/routes.py`](file:///c:/Users/shama/OneDrive/Documents/LLM%20gateway%20project/mini-llm-gateway/app/routes.py).

### Worker Heartbeat Auth
- Workers authenticate heartbeats via an `X-Worker-Secret` header, validated with **HMAC constant-time comparison** against `WORKER_SHARED_SECRET`.
- Implementation: `verify_worker` dependency in [`app/routes.py`](file:///c:/Users/shama/OneDrive/Documents/LLM%20gateway%20project/mini-llm-gateway/app/routes.py).

### Worker Host Allowlist
- `WORKER_ALLOWED_HOSTS` restricts which hostnames can register as workers.
- Empty = all hosts allowed.

### New Config Fields
Added in [`app/config.py`](file:///c:/Users/shama/OneDrive/Documents/LLM%20gateway%20project/mini-llm-gateway/app/config.py):

| Setting | Default | Purpose |
|---|---|---|
| `GATEWAY_API_KEYS` | `""` (disabled) | Comma-separated client API keys |
| `WORKER_SHARED_SECRET` | `"changeme"` | Shared secret for worker heartbeats |
| `WORKER_ALLOWED_HOSTS` | `""` (any) | Comma-separated allowed worker hostnames |
| `MAX_RETRIES` | `2` | Max retry attempts on worker failure |

---

## 🔄 2. Retry & Failover Logic

### How It Works
The `/v1/chat/completions` endpoint now implements **automatic failover** across workers:

```
Request → Worker A (5xx or connection error) → mark OFFLINE → retry Worker B → ...
```

- On **5xx responses** or **connection errors**: the worker is marked `OFFLINE`, and the request is retried on the next least-busy worker.
- On **4xx responses** (e.g., 429 rate limit): the error is returned immediately to the client — **no retry**, worker stays healthy.
- Controlled by `MAX_RETRIES` (default: 2 retries = up to 3 total attempts).
- A set of `tried_workers` prevents re-selecting the same worker.

### Relevant Code
- [`app/routes.py`](file:///c:/Users/shama/OneDrive/Documents/LLM%20gateway%20project/mini-llm-gateway/app/routes.py) — `chat_completions()` retry loop
- [`app/registry.py`](file:///c:/Users/shama/OneDrive/Documents/LLM%20gateway%20project/mini-llm-gateway/app/registry.py) — `get_least_busy_worker(exclude=...)` accepts exclusion set

---

## 📊 3. In-Flight Request Tracking

### Problem (Before)
Worker heartbeats reported `active_requests` and the gateway stored it directly. This meant heartbeats could **reset** the gateway's own tracking of in-flight requests mid-flight.

### Solution (After)
- The gateway now maintains its own `inflight` counter per worker via `acquire_worker()` / `release_worker()` in [`app/registry.py`](file:///c:/Users/shama/OneDrive/Documents/LLM%20gateway%20project/mini-llm-gateway/app/registry.py).
- Heartbeats update metadata (host, port, status, uptime) but **never overwrite** `inflight`.
- `get_least_busy_worker()` selects the worker with the lowest `inflight` count.

---

## 📦 4. Flexible Pydantic Schemas

Changes in [`app/schemas.py`](file:///c:/Users/shama/OneDrive/Documents/LLM%20gateway%20project/mini-llm-gateway/app/schemas.py):

| Change | Why |
|---|---|
| `ChatMessage` has `extra="allow"` | Passes through fields like `tool_calls`, `function_call`, `name` without dropping them |
| `content` is `Optional[Union[str, list]]` | Supports `null` content (tool-call messages) and multimodal content arrays |
| `ChatCompletionRequest` has `extra="allow"` | Passes through vendor-specific fields (e.g., `tools`, `response_format`) |

---

## 🐳 5. Docker Simplification

In [`docker-compose.yml`](file:///c:/Users/shama/OneDrive/Documents/LLM%20gateway%20project/mini-llm-gateway/docker-compose.yml):

**Before:** Two hardcoded services (`worker1`, `worker2`) with duplicated config.

**After:** A single `worker` service with `deploy.replicas: 3`. Workers auto-generate unique names via `worker-{uuid}` and resolve their own hostname via `socket.gethostname()`.

```diff
-  worker1:
-    ...
-    environment:
-      - WORKER_HOST=worker1
-      - WORKER_PORT=8001
-  worker2:
-    ...
-    environment:
-      - WORKER_HOST=worker2
-      - WORKER_PORT=8002
+  worker:
+    ...
+    deploy:
+      replicas: 3
```

---

## ♻️ 6. Worker Lifecycle Modernization

In [`app/worker.py`](file:///c:/Users/shama/OneDrive/Documents/LLM%20gateway%20project/mini-llm-gateway/app/worker.py):

- Replaced deprecated `@app.on_event("startup")` with FastAPI's `lifespan` async context manager.
- Heartbeat task is properly **cancelled** on shutdown.
- Streaming responses now correctly decrement `active_requests` only when the stream finishes (not at the start of `finally`).
- Added `X-Served-By` response header for debugging.

---

## 🖥️ 7. Frontend Updates

In [`app/static/index.html`](file:///c:/Users/shama/OneDrive/Documents/LLM%20gateway%20project/mini-llm-gateway/app/static/index.html) and [`app/static/script.js`](file:///c:/Users/shama/OneDrive/Documents/LLM%20gateway%20project/mini-llm-gateway/app/static/script.js):

- New **API Key input field** in the sidebar, persisted in `localStorage`.
- All fetch calls now include `Authorization: Bearer <key>` header when a key is set.
- SSE error parsing updated to handle structured `{ error: { message, type } }` format.
- Workers and metrics fetch calls handle non-200 responses gracefully.

---

## 🧪 8. Test Coverage

### New Tests

| Test | File | What It Verifies |
|---|---|---|
| `test_heartbeat_preserves_inflight` | [`test_routing.py`](file:///c:/Users/shama/OneDrive/Documents/LLM%20gateway%20project/mini-llm-gateway/tests/test_routing.py) | Heartbeats don't reset gateway's inflight counter |
| `test_routing_picks_lower_inflight` | [`test_routing.py`](file:///c:/Users/shama/OneDrive/Documents/LLM%20gateway%20project/mini-llm-gateway/tests/test_routing.py) | Least-busy selection works correctly |
| `test_retry_on_worker_failure` | [`test_routing.py`](file:///c:/Users/shama/OneDrive/Documents/LLM%20gateway%20project/mini-llm-gateway/tests/test_routing.py) | Request fails over from dead worker to healthy one |
| `test_retry_fails_all` | [`test_routing.py`](file:///c:/Users/shama/OneDrive/Documents/LLM%20gateway%20project/mini-llm-gateway/tests/test_routing.py) | Returns 502 when all workers are unreachable |
| `test_no_retry_on_4xx` | [`test_routing.py`](file:///c:/Users/shama/OneDrive/Documents/LLM%20gateway%20project/mini-llm-gateway/tests/test_routing.py) | 429 errors are not retried; worker stays healthy |
| `test_api_inference_params_and_pass_through` | [`test_worker.py`](file:///c:/Users/shama/OneDrive/Documents/LLM%20gateway%20project/mini-llm-gateway/tests/test_worker.py) | Extra fields like `tool_calls` pass through; null content is handled |
| `test_api_inference_sse_error_quotes` | [`test_worker.py`](file:///c:/Users/shama/OneDrive/Documents/LLM%20gateway%20project/mini-llm-gateway/tests/test_worker.py) | SSE error events produce valid JSON even with special characters |

### Updated Tests
- `test_mock_inference` — Updated assertions for new response format (dict instead of Pydantic model).
- `test_registry` / `test_api` — Aligned with renamed functions and new schema fields.

---

## 📁 Files Changed

```
 .env.example                     |   7 +-
 .github/workflows/test.yml       |  36 +++---
 README.md                        |   8 +-
 app/config.py                    |   7 +
 app/main.py                      |  38 ++++---
 app/registry.py                  |  24 +++-
 app/routes.py                    | 141 ++++++++++++++++++------
 app/schemas.py                   |   8 +-
 app/services/api_inference.py    |  20 +---
 app/services/inference.py        |   2 +-
 app/services/mock_inference.py   |  31 +++--
 app/services/ollama_inference.py | 112 +++++++++++++------
 app/static/index.html            |   3 +
 app/static/script.js             |  29 ++++-
 app/worker.py                    |  47 +++++---
 docker-compose.yml               |  24 +---
 tests/test_api.py                |  33 +++++-
 tests/test_registry.py           |   2 +-
 tests/test_routing.py            | 100 +++++++++++++++++
 tests/test_worker.py             |  80 ++++++++++++++-
```
