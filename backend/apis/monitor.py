from fastapi import APIRouter
from database import get_pool

router = APIRouter(prefix="/monitor")


@router.get("/jobs")
async def monitor_jobs():
    """Return all jobs with their status for the monitor dashboard."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM jobs ORDER BY created_at DESC"
        )
    return [dict(r) for r in rows]


@router.get("/queue")
async def monitor_queue():
    """Return tasks that are queued or in-progress."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT jt.*, j.title as job_title
            FROM job_tasks jt
            JOIN jobs j ON j.id = jt.job_id
            WHERE jt.status IN ('queued', 'running')
            ORDER BY jt.created_at
            """
        )
    return [dict(r) for r in rows]


@router.get("/workers")
async def monitor_workers():
    """Return all worker nodes."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM worker_nodes ORDER BY last_heartbeat DESC NULLS LAST"
        )
    return [dict(r) for r in rows]
