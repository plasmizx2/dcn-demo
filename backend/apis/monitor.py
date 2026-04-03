import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.encoders import jsonable_encoder

from database import get_pool
from config import HEARTBEAT_OFFLINE_SECONDS

logger = logging.getLogger("dcn")

router = APIRouter(prefix="/monitor")


@router.get("/jobs")
async def monitor_jobs() -> list[dict]:
    """Return all jobs with their status for the monitor dashboard."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM jobs ORDER BY created_at DESC"
        )
    return [dict(r) for r in rows]


@router.get("/queue")
async def monitor_queue() -> list[dict]:
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
async def monitor_stats() -> dict:
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
                    WHEN last_heartbeat < NOW() - INTERVAL '{} seconds' THEN 'offline'
                    ELSE status
                END AS effective_status,
                COUNT(*) as count
            FROM worker_nodes
            GROUP BY effective_status
            """.format(HEARTBEAT_OFFLINE_SECONDS)
        )
        worker_counts = {r["effective_status"]: r["count"] for r in worker_rows}

    # Count worker-finished tasks (submitted + awaiting admin validation)
    finished_tasks = task_counts.get("submitted", 0) + task_counts.get(
        "pending_validation", 0
    )

    return {
        "total_jobs": sum(job_counts.values()),
        "completed_jobs": job_counts.get("completed", 0),
        "queued_tasks": task_counts.get("queued", 0),
        "running_tasks": task_counts.get("running", 0),
        "submitted_tasks": finished_tasks,
        "pending_validation_tasks": task_counts.get("pending_validation", 0),
        "online_workers": worker_counts.get("online", 0),
        "busy_workers": worker_counts.get("busy", 0),
    }


@router.get("/workers")
async def monitor_workers() -> list[dict]:
    """Return all worker nodes, marking stale ones as offline."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT *,
                CASE
                    WHEN last_heartbeat IS NULL THEN 'offline'
                    WHEN last_heartbeat < NOW() - INTERVAL '{} seconds' THEN 'offline'
                    ELSE status
                END AS status
            FROM worker_nodes
            ORDER BY last_heartbeat DESC NULLS LAST
            """.format(HEARTBEAT_OFFLINE_SECONDS)
        )
    return [dict(r) for r in rows]


@router.delete("/workers/{worker_id}")
async def delete_worker(worker_id: str, request: Request) -> dict:
    """Admin-only: Remove a worker node entirely."""
    from auth import get_session
    from fastapi import HTTPException
    
    user = await get_session(request)
    from auth import ELEVATED_ROLES
    if not user or user.get("role") not in ELEVATED_ROLES:
        raise HTTPException(status_code=403, detail="Admin access required")
        
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM worker_nodes WHERE id = $1", worker_id
        )
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Worker not found")
            
        # Optional: any running tasks assigned to this worker get requeued immediately
        await conn.execute(
            """
            UPDATE job_tasks 
            SET status = 'queued', worker_node_id = NULL, started_at = NULL 
            WHERE worker_node_id = $1 AND status = 'running'
            """, 
            worker_id
        )
    return {"status": "deleted"}


@router.get("/worker-history/{worker_id}")
async def worker_history(worker_id: str) -> list[dict]:
    """Return task history for a specific worker node."""
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    tr.id,
                    tr.task_id,
                    tr.result_text,
                    tr.execution_time_seconds,
                    tr.status,
                    tr.submitted_at AS created_at,
                    jt.task_name,
                    jt.job_id,
                    j.title AS job_title
                FROM task_results tr
                JOIN job_tasks jt ON jt.id = tr.task_id
                JOIN jobs j ON j.id = jt.job_id
                WHERE tr.worker_node_id = $1::uuid
                ORDER BY tr.submitted_at DESC NULLS LAST
                LIMIT 100
                """,
                worker_id,
            )
    except Exception as e:
        logger.exception("worker_history query failed for worker_id=%s", worker_id)
        raise HTTPException(status_code=500, detail="Failed to load worker history") from e

    return jsonable_encoder([dict(r) for r in rows])
