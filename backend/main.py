import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
from database import get_pool, close_pool
from apis.jobs import router as jobs_router
from apis.monitor import router as monitor_router
from apis.workers import router as workers_router

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend", "public_page")
MONITOR_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend", "monitor")
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend", "results")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start up: connect to DB. Shut down: close connection pool."""
    await get_pool()
    yield
    await close_pool()


app = FastAPI(title="DCN Orchestration Demo", lifespan=lifespan)

app.include_router(jobs_router)
app.include_router(monitor_router)
app.include_router(workers_router)


@app.get("/")
async def serve_frontend():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


@app.get("/ops")
async def serve_monitor():
    return FileResponse(os.path.join(MONITOR_DIR, "index.html"))


@app.get("/results")
async def serve_results():
    return FileResponse(os.path.join(RESULTS_DIR, "index.html"))


@app.get("/health")
async def health():
    """Health check — also verifies DB connection."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.fetchval("SELECT 1")
    return {"status": "ok", "db": "connected"}
