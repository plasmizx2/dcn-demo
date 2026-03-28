import json
from fastapi import APIRouter, HTTPException
from database import get_pool
from schemas import TaskClaim, TaskComplete, WorkerHeartbeat
from aggregator import aggregate_job

router = APIRouter()


@router.post("/tasks/claim")
async def claim_task(body: TaskClaim):
    """Worker claims the next available queued task."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Verify worker exists
        worker = await conn.fetchrow(
            "SELECT id, node_name, status FROM worker_nodes WHERE id = $1",
            body.worker_node_id,
        )
        if not worker:
            raise HTTPException(status_code=404, detail="Worker not found")

        # Claim the oldest queued task atomically using UPDATE ... RETURNING
        # This is safe for hackathon MVP — the single UPDATE with WHERE status='queued'
        # and LIMIT 1 prevents two workers from claiming the same task in Postgres.
        task = await conn.fetchrow(
            """
            UPDATE job_tasks
            SET status = 'running', worker_node_id = $1
            WHERE id = (
                SELECT id FROM job_tasks
                WHERE status = 'queued'
                ORDER BY created_at
                LIMIT 1
                FOR UPDATE SKIP LOCKED
            )
            RETURNING *
            """,
            body.worker_node_id,
        )

        if not task:
            return {"claimed": False, "message": "No queued tasks available"}

        # Update worker status to busy
        await conn.execute(
            "UPDATE worker_nodes SET status = 'busy' WHERE id = $1",
            body.worker_node_id,
        )

        # Log task_started event
        await conn.execute(
            """
            INSERT INTO job_events (job_id, event_type, message)
            VALUES ($1, 'task_started', $2)
            """,
            task["job_id"],
            f"Task {task['id']} claimed by worker {worker['node_name']}",
        )

    return {"claimed": True, "task": dict(task)}


@router.post("/tasks/{task_id}/complete")
async def complete_task(task_id: str, body: TaskComplete = TaskComplete()):
    """Worker marks a task as completed and optionally stores a result."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Verify the task exists and is running
        task = await conn.fetchrow(
            "SELECT * FROM job_tasks WHERE id = $1",
            task_id,
        )
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        if task["status"] != "running":
            raise HTTPException(
                status_code=400,
                detail=f"Task is '{task['status']}', not 'running'",
            )

        # Mark task submitted (worker done, may still need validation)
        updated = await conn.fetchrow(
            "UPDATE job_tasks SET status = 'submitted' WHERE id = $1 RETURNING *",
            task_id,
        )

        # Insert result into task_results (worker_id left null — it references users)
        await conn.execute(
            """
            INSERT INTO task_results (task_id, worker_node_id,
                                      result_text, result_payload,
                                      execution_time_seconds, status)
            VALUES ($1, $2, $3, $4::jsonb, $5, 'submitted')
            """,
            task_id,
            task["worker_node_id"],
            body.result_text or f"Processed task {task_id}",
            json.dumps(body.result_payload) if body.result_payload else "{}",
            body.execution_time_seconds or 0,
        )

        # Set worker back to online
        if task["worker_node_id"]:
            await conn.execute(
                "UPDATE worker_nodes SET status = 'online' WHERE id = $1",
                task["worker_node_id"],
            )

        # Log task_submitted event
        await conn.execute(
            """
            INSERT INTO job_events (job_id, event_type, message)
            VALUES ($1, 'task_submitted', $2)
            """,
            task["job_id"],
            f"Task {task_id} submitted by worker",
        )

        # Check if all tasks done → run aggregation
        aggregated = await aggregate_job(conn, task["job_id"])

    return {
        "completed": True,
        "task": dict(updated),
        "job_aggregated": aggregated,
    }


@router.post("/tasks/{task_id}/fail")
async def fail_task(task_id: str):
    """Mark a task as failed when processing errors out."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        task = await conn.fetchrow(
            "SELECT * FROM job_tasks WHERE id = $1", task_id
        )
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        updated = await conn.fetchrow(
            "UPDATE job_tasks SET status = 'failed' WHERE id = $1 RETURNING *",
            task_id,
        )

        # Set worker back to online
        if task["worker_node_id"]:
            await conn.execute(
                "UPDATE worker_nodes SET status = 'online' WHERE id = $1",
                task["worker_node_id"],
            )

        # Log failure event
        await conn.execute(
            """
            INSERT INTO job_events (job_id, event_type, message)
            VALUES ($1, 'task_failed', $2)
            """,
            task["job_id"],
            f"Task {task_id} failed during processing",
        )

    return {"failed": True, "task": dict(updated)}


@router.post("/workers/heartbeat")
async def worker_heartbeat(body: WorkerHeartbeat):
    """Worker sends a heartbeat to stay active."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.fetchrow(
            """
            UPDATE worker_nodes
            SET last_heartbeat = NOW()
            WHERE id = $1
            RETURNING id, node_name, status, last_heartbeat
            """,
            body.worker_node_id,
        )
        if not result:
            raise HTTPException(status_code=404, detail="Worker not found")

    return dict(result)
