import json
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response
from database import get_pool
from schemas import JobCreate
from planner import plan_tasks
from config import VALID_TASK_TYPES, MIN_PRIORITY, MAX_PRIORITY, MIN_REWARD
from auth import get_session, ELEVATED_ROLES
from pricing import estimate_job_cost, calculate_actual_cost
from rate_limit import check_rate_limit
from aggregator import parse_ml_experiments_from_task_rows, sort_ml_experiments_by_metric
from job_export import (
    build_json_export,
    experiments_to_csv,
    json_dumps_export,
    safe_export_filename,
)

router = APIRouter()


@router.get("/jobs")
async def list_jobs() -> list[dict]:
    """Return all jobs, newest first."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM jobs ORDER BY created_at DESC"
        )
    return [dict(r) for r in rows]


@router.post("/jobs/estimate")
async def estimate_cost(job: JobCreate, request: Request) -> dict:
    """Return a cost estimate for a job without creating it."""
    user = await get_session(request)
    if user and user.get("role") == "waitlister":
        raise HTTPException(
            status_code=403,
            detail="Waitlist accounts cannot estimate or submit jobs yet",
        )
    if job.task_type not in VALID_TASK_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown task type '{job.task_type}'.",
        )
    try:
        subtasks = plan_tasks(job.task_type, job.input_payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return estimate_job_cost(subtasks)


@router.get("/jobs/mine")
async def list_my_jobs(request: Request) -> list[dict]:
    """Return jobs belonging to the authenticated user, newest first."""
    user = await get_session(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not logged in")
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM jobs WHERE user_id = $1::uuid ORDER BY created_at DESC",
            user["id"],
        )
    return [dict(r) for r in rows]


@router.get("/jobs/{job_id}")
async def get_job(job_id: str) -> dict:
    """Return a single job by ID."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM jobs WHERE id = $1", job_id
        )
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    return dict(row)


@router.post("/jobs")
async def create_job(job: JobCreate, request: Request) -> dict:
    """Create a new job, plan subtasks, and log events (transactional)."""
    check_rate_limit(request, max_requests=10, window_seconds=60)  # 10 jobs/min
    user = await get_session(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    if user.get("role") == "waitlister":
        raise HTTPException(
            status_code=403,
            detail="Waitlist accounts cannot submit jobs yet",
        )

    if not job.title or not job.title.strip():
        raise HTTPException(status_code=400, detail="Job title is required")
    if not job.task_type or not job.task_type.strip():
        raise HTTPException(status_code=400, detail="Task type is required")
    if job.task_type not in VALID_TASK_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown task type '{job.task_type}'. Valid types: {', '.join(sorted(VALID_TASK_TYPES))}",
        )
    if not MIN_PRIORITY <= job.priority <= MAX_PRIORITY:
        raise HTTPException(
            status_code=400,
            detail=f"Priority must be between {MIN_PRIORITY} and {MAX_PRIORITY}",
        )
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            # Plan subtasks first so we can price the job
            try:
                subtasks = plan_tasks(job.task_type, job.input_payload)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e)) from e

            # Calculate estimated cost from planned subtasks
            estimate = estimate_job_cost(subtasks)
            reward_amount = estimate["estimated_total"]

            # Insert the job with computed reward_amount
            row = await conn.fetchrow(
                """
                INSERT INTO jobs (title, description, task_type, input_payload,
                                  user_id, priority, reward_amount, requires_validation)
                VALUES ($1, $2, $3, $4::jsonb, $5::uuid, $6, $7, $8)
                RETURNING *
                """,
                job.title,
                job.description,
                job.task_type,
                json.dumps(job.input_payload),
                user["id"],
                job.priority,
                reward_amount,
                job.requires_validation,
            )

            # Log a job_created event
            await conn.execute(
                """
                INSERT INTO job_events (job_id, event_type, message)
                VALUES ($1, 'job_created', 'Job created via API')
                """,
                row["id"],
            )

            # Insert subtasks
            for i, task in enumerate(subtasks, start=1):
                await conn.execute(
                    """
                    INSERT INTO job_tasks (job_id, task_order, task_name, task_description, task_payload, status)
                    VALUES ($1, $2, $3, $4, $5::jsonb, 'queued')
                    """,
                    row["id"],
                    i,
                    task["task_name"],
                    task["task_description"],
                    json.dumps(task["task_payload"]),
                )

            # Log task_split event
            await conn.execute(
                """
                INSERT INTO job_events (job_id, event_type, message)
                VALUES ($1, 'task_split', $2)
                """,
                row["id"],
                f"Job split into {len(subtasks)} tasks",
            )

    result = dict(row)
    result["task_count"] = len(subtasks)
    result["estimated_cost"] = estimate
    return result


@router.get("/jobs/{job_id}/tasks")
async def get_job_tasks(job_id: str) -> list[dict]:
    """Return all tasks for a job, ordered by task_order, with optional failure_detail from task_results."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT jt.*, sub.result_text AS failure_detail
            FROM job_tasks jt
            LEFT JOIN LATERAL (
                SELECT result_text
                FROM task_results
                WHERE task_id = jt.id
                ORDER BY submitted_at DESC
                LIMIT 1
            ) sub ON TRUE
            WHERE jt.job_id = $1
            ORDER BY jt.task_order
            """,
            job_id,
        )
    return [dict(r) for r in rows]


@router.delete("/jobs/all")
async def clear_all_jobs(request: Request) -> dict:
    """Delete all jobs, tasks, events, and results. CEO or admin demo reset."""
    user = await get_session(request)
    if not user or user.get("role") not in ELEVATED_ROLES:
        raise HTTPException(
            status_code=403, detail="CEO or admin access required"
        )
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM task_results")
        await conn.execute("DELETE FROM job_events")
        await conn.execute("DELETE FROM job_tasks")
        await conn.execute("DELETE FROM jobs")
    return {"cleared": True}


@router.delete("/jobs/{job_id}")
async def delete_job(job_id: str, request: Request) -> dict:
    """Delete one job and related tasks, events, and results. Owner or admin/CEO only."""
    try:
        UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Job not found") from None

    user = await get_session(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, user_id FROM jobs WHERE id = $1::uuid", job_id
        )
        if not row:
            raise HTTPException(status_code=404, detail="Job not found")

        owner_id = str(row["user_id"]) if row["user_id"] is not None else None
        is_owner = owner_id == user["id"]
        is_elevated = user.get("role") in ELEVATED_ROLES
        if not is_owner and not is_elevated:
            raise HTTPException(
                status_code=403, detail="You can only delete your own jobs"
            )

        async with conn.transaction():
            await conn.execute(
                """
                DELETE FROM task_results
                WHERE task_id IN (SELECT id FROM job_tasks WHERE job_id = $1::uuid)
                """,
                job_id,
            )
            await conn.execute("DELETE FROM job_tasks WHERE job_id = $1::uuid", job_id)
            await conn.execute(
                "DELETE FROM job_events WHERE job_id = $1::uuid", job_id
            )
            await conn.execute("DELETE FROM jobs WHERE id = $1::uuid", job_id)

    return {"deleted": True, "id": job_id}


@router.get("/jobs/{job_id}/timing")
async def get_job_timing(job_id: str) -> dict:
    """Return parallel vs sequential timing stats for a completed job."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        job = await conn.fetchrow("SELECT * FROM jobs WHERE id = $1", job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        # Get task timing data (include payload + worker for pricing)
        tasks = await conn.fetch(
            """
            SELECT jt.id, jt.task_name, jt.status, jt.started_at, jt.completed_at,
                   jt.task_payload, jt.worker_node_id,
                   tr.execution_time_seconds
            FROM job_tasks jt
            LEFT JOIN task_results tr ON tr.task_id = jt.id
            WHERE jt.job_id = $1
            ORDER BY jt.task_order
            """,
            job_id,
        )

        # Sequential time = sum of all individual execution times
        # (how long one machine would take running tasks back-to-back)
        exec_times = [float(t["execution_time_seconds"]) for t in tasks if t["execution_time_seconds"]]
        sequential_time = sum(exec_times)

        # Parallel time = union of actual execution intervals, merged to
        # remove overlap.  This counts real distributed work time — tasks
        # running concurrently compress the total, but queue gaps (workers
        # busy with OTHER jobs) don't inflate it.
        intervals = sorted(
            [(t["started_at"], t["completed_at"]) for t in tasks
             if t["started_at"] and t["completed_at"]],
            key=lambda x: x[0],
        )

        parallel_time = 0.0
        if intervals:
            merged = [intervals[0]]
            for start, end in intervals[1:]:
                prev_start, prev_end = merged[-1]
                if start <= prev_end:
                    # Overlapping — extend the current interval
                    merged[-1] = (prev_start, max(prev_end, end))
                else:
                    # Gap — start a new interval
                    merged.append((start, end))
            parallel_time = sum(
                (end - start).total_seconds() for start, end in merged
            )

        # Count unique workers
        workers_q = await conn.fetch(
            "SELECT DISTINCT worker_node_id FROM job_tasks WHERE job_id = $1 AND worker_node_id IS NOT NULL",
            job_id,
        )
        worker_ids = [r["worker_node_id"] for r in workers_q]

        speedup = round(sequential_time / parallel_time, 2) if parallel_time > 0 else 0

        task_details = []
        for t in tasks:
            task_details.append({
                "task_name": t["task_name"],
                "status": t["status"],
                "execution_time": float(t["execution_time_seconds"]) if t["execution_time_seconds"] else None,
            })

    # Calculate actual cost from real execution data
    cost_rows = [
        {
            "execution_time_seconds": t["execution_time_seconds"],
            "task_payload": t["task_payload"],
            "worker_node_id": t["worker_node_id"],
        }
        for t in tasks
        if t["execution_time_seconds"]
    ]
    actual_cost = calculate_actual_cost(cost_rows) if cost_rows else None

    seq_s = round(sequential_time, 2)
    par_s = round(parallel_time, 2)
    n_workers = len(worker_ids)
    return {
        "job_id": job_id,
        "status": job["status"],
        "task_type": job["task_type"],
        "total_tasks": len(tasks),
        "sequential_time_seconds": seq_s,
        "parallel_time_seconds": par_s,
        "speedup": speedup,
        "num_workers": n_workers,
        # Aliases for clients that expect shorter names
        "sequential_time": seq_s,
        "parallel_time": par_s,
        "worker_count": n_workers,
        "time_saved": round(max(0.0, sequential_time - parallel_time), 2),
        "estimated_cost": float(job["reward_amount"]),
        "actual_cost": actual_cost,
        "tasks": task_details,
    }


@router.get("/jobs/{job_id}/events")
async def get_job_events(job_id: str) -> list[dict]:
    """Return all events for a job, newest first."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM job_events WHERE job_id = $1 ORDER BY created_at DESC",
            job_id,
        )
    return [dict(r) for r in rows]


@router.get("/jobs/{job_id}/export")
async def export_job_download(
    job_id: str,
    request: Request,
    export_format: Literal["md", "json", "csv"] = Query("md", alias="format"),
):
    """Download completed job output: Markdown report, JSON (ranked metrics + report), or CSV table."""
    try:
        UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Job not found") from None

    user = await get_session(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    pool = await get_pool()
    async with pool.acquire() as conn:
        job = await conn.fetchrow("SELECT * FROM jobs WHERE id = $1::uuid", job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        owner_id = str(job["user_id"]) if job["user_id"] is not None else None
        is_owner = owner_id == user["id"]
        is_elevated = user.get("role") in ELEVATED_ROLES
        if not is_owner and not is_elevated:
            raise HTTPException(
                status_code=403, detail="You can only export your own jobs"
            )

        if job["status"] != "completed" or not job.get("final_output"):
            raise HTTPException(
                status_code=400,
                detail="Job has no completed output to export yet",
            )

        rows = await conn.fetch(
            """
            SELECT jt.task_order, jt.task_name, tr.result_text
            FROM job_tasks jt
            JOIN task_results tr ON tr.task_id = jt.id
            WHERE jt.job_id = $1::uuid AND jt.status = 'submitted'
            ORDER BY jt.task_order
            """,
            job_id,
        )

    job_dict = dict(job)
    results_list = [dict(r) for r in rows]
    experiments = parse_ml_experiments_from_task_rows(results_list)
    ranked = sort_ml_experiments_by_metric(experiments)

    title = job_dict.get("title") or "job"
    if export_format == "md":
        body = job_dict.get("final_output") or ""
        fn = safe_export_filename(title, job_id, "md")
        return Response(
            content=body.encode("utf-8"),
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{fn}"'},
        )
    if export_format == "json":
        payload = build_json_export(job_dict, experiments, ranked)
        fn = safe_export_filename(title, job_id, "json")
        raw = json_dumps_export(payload)
        return Response(
            content=raw.encode("utf-8"),
            media_type="application/json; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{fn}"'},
        )

    csv_body = experiments_to_csv(ranked)
    fn = safe_export_filename(title, job_id, "csv")
    return Response(
        content=csv_body.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{fn}"'},
    )
