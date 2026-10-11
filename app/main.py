import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import asyncio
from contextlib import asynccontextmanager

from app.routes import router
from app.registry import prune_stale_workers
from app.config import settings

async def background_pruner():
    while True:
        stale = prune_stale_workers()
        for name in stale:
            print(f"Gateway: Marked worker {name} as offline")
        await asyncio.sleep(5)

@asynccontextmanager
async def lifespan(app: FastAPI):
    keys = [k.strip() for k in settings.gateway_api_keys.split(",") if k.strip()]
    if not keys:
        print("WARNING: GATEWAY_API_KEYS is empty. Gateway is running without client authentication!")
    task = asyncio.create_task(background_pruner())
    yield
    task.cancel()

app = FastAPI(title="Mini LLM Gateway", lifespan=lifespan)

origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
allow_credentials = origins != ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

static_dir = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir)
    
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
async def serve_frontend():
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Frontend not found"}
