# MiniLLM Gateway

MiniLLM Gateway is a lightweight, distributed API Gateway for Large Language Models. It features a custom load balancer, real-time worker registry, and a stunning built-in glassmorphic web dashboard to monitor your traffic and chat with your models.

## Features
- **Least-Busy Request Routing**: The Gateway routes incoming requests to the worker with the smallest queue depth.
- **Worker Registry & Failover**: Workers send 5-second heartbeats. If a worker goes offline, the gateway instantly stops routing traffic to it.
- **Real-Time Streaming**: Full support for Server-Sent Events (SSE). The gateway proxies streaming chunks instantly back to the client.
- **Global Metrics**: Tracks latency, active requests, successes, and failures across the entire cluster.
- **Web Dashboard**: An out-of-the-box UI served natively by FastAPI to monitor workers and chat with models.

---

## API Endpoints Exposed
- `GET /` - Serves the built-in web dashboard.
- `GET /metrics` - Returns global metrics (latency, active requests, success/fail counts).
- `GET /workers` - Returns the real-time status and metadata of all registered worker nodes.
- `POST /v1/chat/completions` - OpenAI-compatible endpoint. Routes requests to the least-busy worker and supports SSE streaming (`stream: true`).

---

## Supported Inference Engines

The Gateway Workers use a "Strategy" pattern, meaning they can dynamically switch between different LLM backends on a per-request basis simply by reading the requested `model` name from the UI!

### 1. Mock Engine
Used for testing latency and failover mechanics without needing a heavy GPU.
- **How to trigger**: Type exactly `gpt-3.5-turbo` into the dashboard's model selection box.

### 2. Local Ollama Engine
Proxies requests to your local Ollama daemon (e.g., Llama2, Qwen, Mistral).
- **How to trigger**: Prefix your model name with `ollama-`. For example, type `ollama-qwen` or `ollama-llama2`.
- **Config**: Ensure `OLLAMA_URL` is configured in your `.env`.

### 3. Cloud API Engine (OpenAI Compatible)
Proxies requests to external cloud providers (OpenAI, Groq, TogetherAI, Anthropic).
- **How to trigger**: Type *any other model name* (e.g., `gpt-4o`, `claude-3-opus`, `llama3-70b-8192`).
- **Config**: Ensure `API_BASE_URL` and `API_KEY` are configured in your `.env`.

#### Free Cloud API Alternatives
If you do not want to pay for API usage, you can use these free alternatives by simply changing your `.env` variables:
# I am suggesting you guys to use groq as for my testing purpose I have used groq in my local path.

**Option A: Groq (Lightning Fast & Free)**
* `API_BASE_URL=https://api.groq.com/openai/v1`
* `API_KEY=gsk_your_free_groq_key`
* **Models to type in UI**: `llama-3.1-8b-instant`, `mixtral-8x7b-32768`

**Option B: OpenRouter (Free Tier Models)**
* `API_BASE_URL=https://openrouter.ai/api/v1`
* `API_KEY=sk-or-v1-your_free_openrouter_key`
* **Models to type in UI**: `openai/gpt-oss-120b`, `meta-llama/llama-3-8b-instruct:free`

---

## Setup & Configuration

1. **Environment Variables**:
   Copy the example config to create your `.env` file:
   ```bash
   cp .env.example .env
   ```
   Add your API Keys or custom URLs to the `.env` file:
   ```ini
   WORKER_GATEWAY_URL=http://gateway:8000
   OLLAMA_URL=http://host.docker.internal:11434
   
   # For External Cloud APIs (OpenAI, Groq, etc)
   API_BASE_URL=https://api.openai.com/v1
   API_KEY=sk-your-api-key-here
   ```

2. **Run the Cluster**:
   The entire system is containerized with Docker.
   ```bash
   docker-compose up --build
   ```

3. **Horizontal Scaling (Handling More Users)**:
   You can easily scale the number of worker nodes to handle more concurrent users without changing any code. The gateway will automatically detect new workers and load-balance across them:
   ```bash
   docker-compose up --build --scale worker=5
   ```

4. **Open the Dashboard**:
   Navigate to `http://localhost:8000` in your web browser. 
   
## Architecture
Check out `architecture.html` in the root folder for an interactive Mermaid diagram of how the distributed components talk to each other!
