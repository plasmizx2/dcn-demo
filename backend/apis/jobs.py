import json
from fastapi import APIRouter, HTTPException
from database import get_pool
from schemas import JobCreate
from planner import plan_tasks

router = APIRouter()


@router.get("/jobs")
async def list_jobs():
    """Return all jobs, newest first."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM jobs ORDER BY created_at DESC"
        )
    return [dict(r) for r in rows]


@router.get("/jobs/{job_id}")
async def get_job(job_id: str):
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
async def create_job(job: JobCreate):
    """Create a new job and log a job_created event."""
    pool = await get_pool()
    async with pool.acquire() as conn:
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

    return dict(row)


@router.get("/jobs/{job_id}/tasks")
async def get_job_tasks(job_id: str):
    """Return all tasks for a job, ordered by task_order."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM job_tasks WHERE job_id = $1 ORDER BY task_order",
            job_id,
        )
    return [dict(r) for r in rows]


@router.delete("/jobs/all")
async def clear_all_jobs():
    """Delete all jobs, tasks, events, and results. Demo reset."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM task_results")
        await conn.execute("DELETE FROM job_events")
        await conn.execute("DELETE FROM job_tasks")
        await conn.execute("DELETE FROM jobs")
    return {"cleared": True}


@router.get("/jobs/{job_id}/events")
async def get_job_events(job_id: str):
    """Return all events for a job, newest first."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM job_events WHERE job_id = $1 ORDER BY created_at DESC",
            job_id,
        )
    return [dict(r) for r in rows]
