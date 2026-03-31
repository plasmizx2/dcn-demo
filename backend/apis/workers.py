import json
from fastapi import APIRouter, HTTPException
from database import get_pool
from schemas import TaskClaim, TaskComplete, TaskFail, WorkerHeartbeat, WorkerRegister, CacheLookup, CacheStore
from aggregator import aggregate_job

router = APIRouter()


@router.post("/workers/register")
async def register_worker(body: WorkerRegister) -> dict:
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
async def claim_task(body: TaskClaim) -> dict:
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

        # Build claim query — filter by supported task types, enforce min_tier,
        # and prioritize: tasks matching the worker's own tier first (so T4
        # workers grab T4 work before falling back to easier tasks), then by
        # job priority, then FIFO.
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
                    ORDER BY (COALESCE((jt.task_payload->>'min_tier')::int, 1) = $3) DESC,
                             j.priority DESC,
                             COALESCE((jt.task_payload->>'min_tier')::int, 1) DESC,
                             jt.created_at
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
                    ORDER BY (COALESCE((jt.task_payload->>'min_tier')::int, 1) = $2) DESC,
                             j.priority DESC,
                             COALESCE((jt.task_payload->>'min_tier')::int, 1) DESC,
                             jt.created_at
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
async def complete_task(task_id: str, body: TaskComplete = TaskComplete()) -> dict:
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

            # Check if the parent job requires validation
            job = await conn.fetchrow(
                "SELECT requires_validation FROM jobs WHERE id = $1",
                task["job_id"],
            )
            needs_validation = job["requires_validation"] if job else False
            new_status = "pending_validation" if needs_validation else "submitted"

            # Mark task as submitted or pending_validation
            updated = await conn.fetchrow(
                "UPDATE job_tasks SET status = $2, completed_at = NOW() WHERE id = $1 RETURNING *",
                task_id,
                new_status,
            )

            # Insert result into task_results (worker_id left null — it references users)
            await conn.execute(
                """
                INSERT INTO task_results (task_id, worker_node_id,
                                          result_text, result_payload,
                                          execution_time_seconds, status)
                VALUES ($1, $2, $3, $4::jsonb, $5, $6)
                """,
                task_id,
                task["worker_node_id"],
                body.result_text or f"Processed task {task_id}",
                json.dumps(body.result_payload) if body.result_payload else "{}",
                body.execution_time_seconds or 0,
                new_status,
            )

            # Set worker back to online
            if task["worker_node_id"]:
                await conn.execute(
                    "UPDATE worker_nodes SET status = 'online' WHERE id = $1",
                    task["worker_node_id"],
                )

            # Log event
            event_msg = f"Task {task_id} {'pending validation' if needs_validation else 'submitted'} by worker"
            await conn.execute(
                """
                INSERT INTO job_events (job_id, event_type, message)
                VALUES ($1, $2, $3)
                """,
                task["job_id"],
                "task_pending_validation" if needs_validation else "task_submitted",
                event_msg,
            )

            # Only run aggregation if no validation needed
            aggregated = False
            if not needs_validation:
                aggregated = await aggregate_job(conn, task["job_id"])

    return {
        "completed": True,
        "task": dict(updated),
        "job_aggregated": aggregated,
    }


@router.post("/tasks/{task_id}/validate")
async def validate_task(task_id: str) -> dict:
    """Admin validates a pending task, moving it to 'submitted' status.

    Once all tasks for a job are validated (submitted), aggregation runs.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            task = await conn.fetchrow(
                "SELECT * FROM job_tasks WHERE id = $1", task_id
            )
            if not task:
                raise HTTPException(status_code=404, detail="Task not found")
            if task["status"] != "pending_validation":
                raise HTTPException(
                    status_code=400,
                    detail=f"Task is '{task['status']}', not 'pending_validation'",
                )

            # Approve: move to submitted
            updated = await conn.fetchrow(
                "UPDATE job_tasks SET status = 'submitted' WHERE id = $1 RETURNING *",
                task_id,
            )

            # Also update task_results status
            await conn.execute(
                "UPDATE task_results SET status = 'submitted' WHERE task_id = $1",
                task_id,
            )

            # Log validation event
            await conn.execute(
                """
                INSERT INTO job_events (job_id, event_type, message)
                VALUES ($1, 'task_validated', $2)
                """,
                task["job_id"],
                f"Task {task_id} validated by admin",
            )

            # Check if all tasks are now submitted → aggregate
            aggregated = await aggregate_job(conn, task["job_id"])

    return {
        "validated": True,
        "task": dict(updated),
        "job_aggregated": aggregated,
    }


@router.post("/tasks/{task_id}/fail")
async def fail_task(task_id: str, body: TaskFail = TaskFail()) -> dict:
    """Mark a task as failed when processing errors out. Optional worker error text is logged."""
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

        err = (body.error or "").strip()
        if len(err) > 4000:
            err = err[:4000] + "…"
        msg = (
            f"Task {task_id} failed: {err}"
            if err
            else f"Task {task_id} failed during processing"
        )

        # Log failure event (visible in /ops event feed)
        await conn.execute(
            """
            INSERT INTO job_events (job_id, event_type, message)
            VALUES ($1, 'task_failed', $2)
            """,
            task["job_id"],
            msg,
        )

        # Store on task_results so job detail table can show the reason (not just "failed")
        await conn.execute("DELETE FROM task_results WHERE task_id = $1", task_id)
        await conn.execute(
            """
            INSERT INTO task_results (task_id, worker_node_id, result_text, result_payload, status)
            VALUES ($1, $2, $3, '{}'::jsonb, 'failed')
            """,
            task_id,
            task["worker_node_id"],
            msg,
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
async def worker_heartbeat(body: WorkerHeartbeat) -> dict:
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


@router.post("/tasks/cache/lookup")
async def cache_lookup(body: CacheLookup) -> dict:
    """Check if an LLM prompt response is already cached."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT response_text FROM llm_cache WHERE prompt_hash = $1",
            body.prompt_hash,
        )
        if row:
            return {"hit": True, "response_text": row["response_text"]}
        return {"hit": False}


@router.post("/tasks/cache/store")
async def cache_store(body: CacheStore) -> dict:
    """Store an LLM prompt response in the cache."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO llm_cache (prompt_hash, response_text)
            VALUES ($1, $2)
            ON CONFLICT (prompt_hash) DO NOTHING
            """,
            body.prompt_hash,
            body.response_text,
        )
    return {"status": "stored"}
