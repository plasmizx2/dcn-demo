import json
from fastapi import APIRouter, HTTPException, Request
from database import get_pool
from auth import get_session, ELEVATED_ROLES


router = APIRouter()


async def _require_job_access(conn, request: Request, job_id: str) -> dict:
    user = await get_session(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    job = await conn.fetchrow("SELECT id, user_id, task_type, status FROM jobs WHERE id = $1::uuid", job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["task_type"] != "local_llm_chat":
        raise HTTPException(status_code=400, detail="Not a local_llm_chat job")

    is_owner = (str(job["user_id"]) if job["user_id"] is not None else None) == user["id"]
    is_admin = user.get("role") in ELEVATED_ROLES
    if not is_owner and not is_admin:
        raise HTTPException(status_code=403, detail="You can only access your own chat jobs")

    return dict(job)


@router.get("/chat/{job_id}/messages")
async def get_chat_messages(request: Request, job_id: str, after_seq: int = 0) -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await _require_job_access(conn, request, job_id)

        rows = await conn.fetch(
            """
            SELECT seq, role, content, created_at
            FROM chat_messages
            WHERE job_id = $1::uuid AND seq > $2
            ORDER BY seq ASC
            """,
            job_id,
            after_seq,
        )
        return [dict(r) for r in rows]


@router.get("/chat/worker/{job_id}/messages")
async def worker_get_chat_messages(job_id: str, after_seq: int = 0) -> list[dict]:
    """
    Worker-facing message feed.

    This endpoint is intentionally unauthenticated so workers can poll for new user messages
    while executing the local inference loop.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        job = await conn.fetchrow("SELECT id, task_type FROM jobs WHERE id = $1::uuid", job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        if job["task_type"] != "local_llm_chat":
            raise HTTPException(status_code=400, detail="Not a local_llm_chat job")

        rows = await conn.fetch(
            """
            SELECT seq, role, content, created_at
            FROM chat_messages
            WHERE job_id = $1::uuid AND seq > $2
            ORDER BY seq ASC
            """,
            job_id,
            after_seq,
        )
        return [dict(r) for r in rows]


@router.post("/chat/{job_id}/message")
async def post_user_message(job_id: str, request: Request) -> dict:
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON") from None

    content = (body.get("content") or "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="content is required")
    if len(content) > 4000:
        raise HTTPException(status_code=400, detail="content too long (max 4000 chars)")

    pool = await get_pool()
    async with pool.acquire() as conn:
        await _require_job_access(conn, request, job_id)

        # Next seq is max(seq)+1 within job.
        next_seq = await conn.fetchval(
            "SELECT COALESCE(MAX(seq), 0) + 1 FROM chat_messages WHERE job_id = $1::uuid",
            job_id,
        )
        await conn.execute(
            """
            INSERT INTO chat_messages (job_id, seq, role, content)
            VALUES ($1::uuid, $2, 'user', $3)
            """,
            job_id,
            next_seq,
            content,
        )
        await conn.execute(
            """
            INSERT INTO job_events (job_id, event_type, message)
            VALUES ($1::uuid, 'chat_user_message', $2)
            """,
            job_id,
            f"User message received (seq={next_seq})",
        )

    return {"ok": True, "seq": int(next_seq)}


# ── Worker-facing streaming helpers (no user auth) ─────────────────

@router.post("/chat/worker/{job_id}/assistant/start")
async def worker_start_assistant_message(job_id: str, request: Request) -> dict:
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON") from None
    worker_node_id = (body.get("worker_node_id") or "").strip()
    if not worker_node_id:
        raise HTTPException(status_code=400, detail="worker_node_id is required")

    pool = await get_pool()
    async with pool.acquire() as conn:
        job = await conn.fetchrow("SELECT id, task_type FROM jobs WHERE id = $1::uuid", job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        if job["task_type"] != "local_llm_chat":
            raise HTTPException(status_code=400, detail="Not a local_llm_chat job")

        next_seq = await conn.fetchval(
            "SELECT COALESCE(MAX(seq), 0) + 1 FROM chat_messages WHERE job_id = $1::uuid",
            job_id,
        )
        await conn.execute(
            """
            INSERT INTO chat_messages (job_id, seq, role, content)
            VALUES ($1::uuid, $2, 'assistant', '')
            """,
            job_id,
            next_seq,
        )
        await conn.execute(
            """
            INSERT INTO job_events (job_id, event_type, message)
            VALUES ($1::uuid, 'chat_assistant_start', $2)
            """,
            job_id,
            f"Worker {worker_node_id[:8]} started assistant response (seq={next_seq})",
        )

    return {"ok": True, "seq": int(next_seq)}


@router.post("/chat/worker/{job_id}/assistant/chunk")
async def worker_append_assistant_chunk(job_id: str, request: Request) -> dict:
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON") from None

    worker_node_id = (body.get("worker_node_id") or "").strip()
    seq = body.get("seq")
    chunk = body.get("chunk")
    if not worker_node_id:
        raise HTTPException(status_code=400, detail="worker_node_id is required")
    if not isinstance(seq, int) or seq <= 0:
        raise HTTPException(status_code=400, detail="seq must be a positive integer")
    if not isinstance(chunk, str) or not chunk:
        raise HTTPException(status_code=400, detail="chunk is required")
    if len(chunk) > 2000:
        raise HTTPException(status_code=400, detail="chunk too long")

    pool = await get_pool()
    async with pool.acquire() as conn:
        updated = await conn.execute(
            """
            UPDATE chat_messages
            SET content = content || $3
            WHERE job_id = $1::uuid AND seq = $2 AND role = 'assistant'
            """,
            job_id,
            seq,
            chunk,
        )
        # best-effort event (not for every token; workers can throttle)
        if updated:
            pass

    return {"ok": True}


@router.post("/chat/worker/{job_id}/event")
async def worker_chat_event(job_id: str, request: Request) -> dict:
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON") from None
    worker_node_id = (body.get("worker_node_id") or "").strip()
    event_type = (body.get("event_type") or "").strip()
    message = (body.get("message") or "").strip()
    if not worker_node_id:
        raise HTTPException(status_code=400, detail="worker_node_id is required")
    if not event_type:
        raise HTTPException(status_code=400, detail="event_type is required")
    if not message:
        raise HTTPException(status_code=400, detail="message is required")
    if len(message) > 4000:
        message = message[:4000] + "…"

    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO job_events (job_id, event_type, message)
            VALUES ($1::uuid, $2, $3)
            """,
            job_id,
            f"chat_{event_type}",
            f"[{worker_node_id[:8]}] {message}",
        )
    return {"ok": True}

