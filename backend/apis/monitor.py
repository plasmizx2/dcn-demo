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


@router.get("/stats")
async def monitor_stats():
    """Return aggregate counts for the dashboard stats bar."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Task counts by status
        task_rows = await conn.fetch(
            "SELECT status, COUNT(*) as count FROM job_tasks GROUP BY status"
        )
        task_counts = {r["status"]: r["count"] for r in task_rows}

        # Job counts
        job_rows = await conn.fetch(
            "SELECT status, COUNT(*) as count FROM jobs GROUP BY status"
        )
        job_counts = {r["status"]: r["count"] for r in job_rows}

        # Worker counts (with heartbeat timeout)
        worker_rows = await conn.fetch(
            """
            SELECT
                CASE
                    WHEN last_heartbeat IS NULL THEN 'offline'
                    WHEN last_heartbeat < NOW() - INTERVAL '30 seconds' THEN 'offline'
                    ELSE status
                END AS effective_status,
                COUNT(*) as count
            FROM worker_nodes
            GROUP BY effective_status
            """
        )
        worker_counts = {r["effective_status"]: r["count"] for r in worker_rows}

    return {
        "total_jobs": sum(job_counts.values()),
        "completed_jobs": job_counts.get("completed", 0),
        "queued_tasks": task_counts.get("queued", 0),
        "running_tasks": task_counts.get("running", 0),
        "submitted_tasks": task_counts.get("submitted", 0),
        "online_workers": worker_counts.get("online", 0),
        "busy_workers": worker_counts.get("busy", 0),
    }


@router.get("/workers")
async def monitor_workers():
    """Return all worker nodes, marking stale ones as offline."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT *,
                CASE
                    WHEN last_heartbeat IS NULL THEN 'offline'
                    WHEN last_heartbeat < NOW() - INTERVAL '30 seconds' THEN 'offline'
                    ELSE status
                END AS status
            FROM worker_nodes
            ORDER BY last_heartbeat DESC NULLS LAST
            """
        )
    return [dict(r) for r in rows]
