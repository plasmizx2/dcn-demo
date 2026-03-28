from fastapi import FastAPI
from contextlib import asynccontextmanager
from database import get_pool, close_pool
from apis.jobs import router as jobs_router
from apis.monitor import router as monitor_router
from apis.workers import router as workers_router


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


@app.get("/health")
async def health():
    """Health check — also verifies DB connection."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.fetchval("SELECT 1")
    return {"status": "ok", "db": "connected"}
