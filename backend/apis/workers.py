import json
from fastapi import APIRouter, HTTPException
from database import get_pool
from schemas import TaskClaim, TaskComplete, WorkerHeartbeat, WorkerRegister
from aggregator import aggregate_job

router = APIRouter()


@router.post("/workers/register")
async def register_worker(body: WorkerRegister):
    """Register a new worker node. Returns the worker UUID."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO worker_nodes (node_name, status)
            VALUES ($1, 'online')
            RETURNING id, node_name, status
            """,
            body.node_name,
        )
    return dict(row)


@router.post("/tasks/claim")
async def claim_task(body: TaskClaim):
    """Worker claims the next available queued task, optionally filtered by task type."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Verify worker exists
        worker = await conn.fetchrow(
            "SELECT id, node_name, status FROM worker_nodes WHERE id = $1",
            body.worker_node_id,
        )
        if not worker:
            raise HTTPException(status_code=404, detail="Worker not found")

        # Build claim query — optionally filter by task types the worker supports, enforce min_tier, and prioritize high difficulty tasks
        if body.task_types:
            task = await conn.fetchrow(
                """
                UPDATE job_tasks
                SET status = 'running', worker_node_id = $1, started_at = NOW()
                WHERE id = (
                    SELECT jt.id FROM job_tasks jt
                    JOIN jobs j ON j.id = jt.job_id
                    WHERE jt.status = 'queued'
                      AND j.task_type = ANY($2)
                      AND COALESCE((jt.task_payload->>'min_tier')::int, 1) <= $3
                    ORDER BY j.priority DESC, COALESCE((jt.task_payload->>'min_tier')::int, 1) DESC, jt.created_at
                    LIMIT 1
                    FOR UPDATE OF jt SKIP LOCKED
                )
                RETURNING *
                """,
                body.worker_node_id,
                body.task_types,
                body.worker_tier,
            )
        else:
            task = await conn.fetchrow(
                """
                UPDATE job_tasks
                SET status = 'running', worker_node_id = $1, started_at = NOW()
                WHERE id = (
                    SELECT jt.id FROM job_tasks jt
                    JOIN jobs j ON j.id = jt.job_id
                    WHERE jt.status = 'queued'
                      AND COALESCE((jt.task_payload->>'min_tier')::int, 1) <= $2
                    ORDER BY j.priority DESC, COALESCE((jt.task_payload->>'min_tier')::int, 1) DESC, jt.created_at
                    LIMIT 1
                    FOR UPDATE OF jt SKIP LOCKED
                )
                RETURNING *
                """,
                body.worker_node_id,
                body.worker_tier,
            )

        if not task:
            return {"claimed": False, "message": "No queued tasks available"}

        # Update worker status to busy
        await conn.execute(
            "UPDATE worker_nodes SET status = 'busy' WHERE id = $1",
            body.worker_node_id,
        )

        # Mark job as running when the first task is claimed
        await conn.execute(
            """
            UPDATE jobs SET status = 'running', updated_at = NOW()
            WHERE id = $1 AND status = 'queued'
            """,
            task["job_id"],
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
        async with conn.transaction():
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
                "UPDATE job_tasks SET status = 'submitted', completed_at = NOW() WHERE id = $1 RETURNING *",
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

        # If all tasks are terminal (submitted or failed), mark job as failed
        counts = await conn.fetchrow(
            """
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE status IN ('submitted', 'failed')) AS done
            FROM job_tasks WHERE job_id = $1
            """,
            task["job_id"],
        )
        if counts["done"] >= counts["total"]:
            # Check if any submitted — if so, aggregation will handle it; otherwise job failed
            submitted = await conn.fetchval(
                "SELECT COUNT(*) FROM job_tasks WHERE job_id = $1 AND status = 'submitted'",
                task["job_id"],
            )
            if submitted == 0:
                await conn.execute(
                    "UPDATE jobs SET status = 'failed', updated_at = NOW() WHERE id = $1",
                    task["job_id"],
                )
                await conn.execute(
                    """
                    INSERT INTO job_events (job_id, event_type, message)
                    VALUES ($1, 'job_failed', 'All tasks failed')
                    """,
                    task["job_id"],
                )
            else:
                await aggregate_job(conn, task["job_id"])

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
