import json
from fastapi import APIRouter, HTTPException
from database import get_pool
from schemas import JobCreate
from planner import plan_tasks

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
async def create_job(job: JobCreate) -> dict:
    """Create a new job, plan subtasks, and log events (transactional)."""
    if not job.title or not job.title.strip():
        raise HTTPException(status_code=400, detail="Job title is required")
    if not job.task_type or not job.task_type.strip():
        raise HTTPException(status_code=400, detail="Task type is required")

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            # Insert the job
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
                job.user_id,
                job.priority,
                job.reward_amount,
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

            # Plan and insert subtasks
            subtasks = plan_tasks(job.task_type, job.input_payload)
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
    return result


@router.get("/jobs/{job_id}/tasks")
async def get_job_tasks(job_id: str) -> list[dict]:
    """Return all tasks for a job, ordered by task_order."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM job_tasks WHERE job_id = $1 ORDER BY task_order",
            job_id,
        )
    return [dict(r) for r in rows]


@router.delete("/jobs/all")
async def clear_all_jobs() -> dict:
    """Delete all jobs, tasks, events, and results. Demo reset."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM task_results")
        await conn.execute("DELETE FROM job_events")
        await conn.execute("DELETE FROM job_tasks")
        await conn.execute("DELETE FROM jobs")
    return {"cleared": True}


@router.get("/jobs/{job_id}/timing")
async def get_job_timing(job_id: str) -> dict:
    """Return parallel vs sequential timing stats for a completed job."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        job = await conn.fetchrow("SELECT * FROM jobs WHERE id = $1", job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        # Get task timing data
        tasks = await conn.fetch(
            """
            SELECT jt.id, jt.task_name, jt.status, jt.started_at, jt.completed_at,
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

    return {
        "job_id": job_id,
        "status": job["status"],
        "task_type": job["task_type"],
        "total_tasks": len(tasks),
        "sequential_time_seconds": round(sequential_time, 2),
        "parallel_time_seconds": round(parallel_time, 2),
        "speedup": speedup,
        "num_workers": len(worker_ids),
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
