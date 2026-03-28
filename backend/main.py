import os
import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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


async def _maintenance_loop():
    """Background task: reap stale tasks (>8min running) and prune dead workers (>1hr no heartbeat)."""
    while True:
        await asyncio.sleep(60)
        try:
            pool = await get_pool()
            async with pool.acquire() as conn:
                # Reap stale running tasks → move back to queued
                # Uses started_at (set when worker claims the task)
                reaped = await conn.fetch(
                    """
                    UPDATE job_tasks
                    SET status = 'queued', worker_node_id = NULL, started_at = NULL
                    WHERE status = 'running'
                      AND started_at IS NOT NULL
                      AND started_at < NOW() - INTERVAL '8 minutes'
                    RETURNING id, job_id
                    """,
                )
                for row in reaped:
                    await conn.execute(
                        """
                        INSERT INTO job_events (job_id, event_type, message)
                        VALUES ($1, 'task_requeued', $2)
                        """,
                        row["job_id"],
                        f"Task {row['id']} requeued after 8min timeout",
                    )
                    print(f"[maintenance] Reaped stale task {str(row['id'])[:8]}")

                # Prune dead workers (no heartbeat for >1 hour)
                pruned = await conn.fetch(
                    """
                    DELETE FROM worker_nodes
                    WHERE last_heartbeat < NOW() - INTERVAL '1 hour'
                       OR (last_heartbeat IS NULL AND created_at < NOW() - INTERVAL '1 hour')
                    RETURNING id, node_name
                    """,
                )
                for row in pruned:
                    print(f"[maintenance] Pruned dead worker: {row['node_name']} ({str(row['id'])[:8]})")

        except Exception as e:
            print(f"[maintenance] Error: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start up: connect to DB + start maintenance. Shut down: clean up."""
    await get_pool()
    maintenance_task = asyncio.create_task(_maintenance_loop())
    yield
    maintenance_task.cancel()
    await close_pool()


app = FastAPI(title="DCN Orchestration Demo", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
