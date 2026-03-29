import logging
import os
import asyncio
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse, JSONResponse
from contextlib import asynccontextmanager
from database import get_pool, close_pool
from apis.jobs import router as jobs_router
from apis.monitor import router as monitor_router
from apis.workers import router as workers_router
from auth import (
    verify_user, create_session, get_session, destroy_session,
    hash_password, SESSION_COOKIE, ADMIN_PAGES, ADMIN_API_PREFIXES, PUBLIC_PREFIXES,
)
from config import (
    MAINTENANCE_INTERVAL_SECONDS, STALE_TASK_TIMEOUT_MINUTES,
    WORKER_PRUNE_TIMEOUT_MINUTES, SESSION_MAX_AGE_SECONDS,
)

logger = logging.getLogger("dcn")

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend", "public_page")
MONITOR_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend", "monitor")
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend", "results")
LANDING_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend", "landing")
LOGIN_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend", "login")
MYJOBS_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend", "my-jobs")
ERROR_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend", "error")
WORKER_LOGS_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend", "worker-logs")


async def _maintenance_loop():
    """Background task: reap stale tasks (>8min running) and prune dead workers (>1hr no heartbeat)."""
    while True:
        await asyncio.sleep(MAINTENANCE_INTERVAL_SECONDS)
        try:
            pool = await get_pool()
            async with pool.acquire() as conn:
                # Reap stale running tasks → move back to queued
                # Uses started_at (set when worker claims the task)
                reaped = await conn.fetch(
                    """
                    UPDATE job_tasks
                    SET status = 'queued', worker_node_id = NULL, started_at = NULL
                    WHERE status = 'running'
                      AND started_at IS NOT NULL
                      AND started_at < NOW() - INTERVAL '{} minutes'
                    RETURNING id, job_id
                    """.format(STALE_TASK_TIMEOUT_MINUTES),
                )
                for row in reaped:
                    await conn.execute(
                        """
                        INSERT INTO job_events (job_id, event_type, message)
                        VALUES ($1, 'task_requeued', $2)
                        """,
                        row["job_id"],
                    f"Task {row['id']} requeued after {STALE_TASK_TIMEOUT_MINUTES}min timeout",
                    )
                    logger.info("Reaped stale task %s", str(row['id'])[:8])

                # Prune dead workers (no heartbeat for >1 hour)
                pruned = await conn.fetch(
                    """
                    DELETE FROM worker_nodes
                    WHERE last_heartbeat < NOW() - INTERVAL '{} minutes'
                       OR (last_heartbeat IS NULL AND created_at < NOW() - INTERVAL '{} minutes')
                    RETURNING id, node_name
                    """.format(WORKER_PRUNE_TIMEOUT_MINUTES, WORKER_PRUNE_TIMEOUT_MINUTES),
                )
                for row in pruned:
                    logger.info("Pruned dead worker: %s (%s)", row['node_name'], str(row['id'])[:8])

        except Exception as e:
            logger.error("Maintenance loop error: %s", e, exc_info=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start up: connect to DB, create static cache table, + start maintenance. Shut down: clean up."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS llm_cache (
                prompt_hash         TEXT PRIMARY KEY,
                response_text       TEXT NOT NULL,
                created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS dcn_users (
                id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                username            TEXT UNIQUE NOT NULL,
                password_hash       TEXT NOT NULL,
                role                TEXT NOT NULL,
                created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token_id            TEXT PRIMARY KEY,
                user_id             UUID NOT NULL REFERENCES dcn_users(id) ON DELETE CASCADE,
                created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            """
        )
        
        # Seed default users if empty
        count = await conn.fetchval("SELECT COUNT(*) FROM dcn_users")
        if count == 0:
            admin_pwd = hash_password("admin123")
            customer_pwd = hash_password("customer123")
            await conn.execute(
                "INSERT INTO dcn_users (username, password_hash, role) VALUES ($1, $2, 'admin')", "admin", admin_pwd
            )
            await conn.execute(
                "INSERT INTO dcn_users (username, password_hash, role) VALUES ($1, $2, 'customer')", "customer", customer_pwd
            )
    maintenance_task = asyncio.create_task(_maintenance_loop())
    yield
    maintenance_task.cancel()
    await close_pool()


app = FastAPI(title="DCN Orchestration Demo", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(jobs_router)
app.include_router(monitor_router)
app.include_router(workers_router)


# ── Auth middleware ──────────────────────────────────────────────
@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    path = request.url.path

    # Let public routes, worker endpoints, and static assets through
    if any(path.startswith(p) for p in PUBLIC_PREFIXES):
        return await call_next(request)

    # Admin-only pages → redirect to login if not admin
    if path in ADMIN_PAGES:
        user = await get_session(request)
        if not user:
            return RedirectResponse("/login", status_code=302)
        if user["role"] != "admin":
            return RedirectResponse("/login", status_code=302)

    # Admin-only API routes → 401 JSON if not admin
    if any(path.startswith(p) for p in ADMIN_API_PREFIXES):
        user = await get_session(request)
        if not user or user["role"] != "admin":
            return JSONResponse({"detail": "Admin access required"}, status_code=401)

    return await call_next(request)


# ── Auth routes ─────────────────────────────────────────────────
@app.get("/login")
async def serve_login(request: Request):
    # Already logged in? Redirect to appropriate page
    user = await get_session(request)
    if user:
        return RedirectResponse("/ops" if user["role"] == "admin" else "/submit")
    return FileResponse(os.path.join(LOGIN_DIR, "index.html"))


@app.post("/auth/login")
async def do_login(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"detail": "Invalid JSON body"}, status_code=400)
    username = body.get("username", "")
    password = body.get("password", "")

    user = await verify_user(username, password)
    if not user:
        return JSONResponse({"detail": "Invalid username or password"}, status_code=401)

    token = await create_session(user)
    redirect = "/ops" if user["role"] == "admin" else "/submit"
    response = JSONResponse({"ok": True, "role": user["role"], "name": user.get("name", user["username"]), "redirect": redirect})
    response.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="lax", max_age=SESSION_MAX_AGE_SECONDS)
    return response


@app.post("/auth/register")
async def do_register(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"detail": "Invalid JSON body"}, status_code=400)
    username = body.get("username", "")
    password = body.get("password", "")

    if not username or not password:
        return JSONResponse({"detail": "Username and password required"}, status_code=400)
    if len(username) < 3:
        return JSONResponse({"detail": "Username must be at least 3 characters"}, status_code=400)
    if len(password) < 6:
        return JSONResponse({"detail": "Password must be at least 6 characters"}, status_code=400)

    pool = await get_pool()
    pwd_hash = hash_password(password)

    async with pool.acquire() as conn:
        try:
            # Safely attempt to create user
            new_id = await conn.fetchval(
                "INSERT INTO dcn_users (username, password_hash, role) VALUES ($1, $2, 'customer') RETURNING id",
                username, pwd_hash
            )
        except Exception as e:
            # asyncpg UniqueViolationError (username taken) or other DB errors
            logger.warning("Registration failed for %s: %s", username, e)
            return JSONResponse({"detail": "Username is already taken"}, status_code=400)

    # Immediately log them in
    user = await verify_user(username, password)
    if not user:
        return JSONResponse({"detail": "Registration succeeded but login failed"}, status_code=500)
    token = await create_session(user)
    
    redirect = "/submit"
    response = JSONResponse({"ok": True, "role": user["role"], "name": user["username"], "redirect": redirect})
    response.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="lax", max_age=SESSION_MAX_AGE_SECONDS)
    return response


@app.get("/auth/me")
async def auth_me(request: Request):
    user = await get_session(request)
    if not user:
        return JSONResponse({"detail": "Not logged in"}, status_code=401)
    return {"username": user["username"], "role": user["role"], "name": user.get("name", user["username"])}


@app.api_route("/auth/logout", methods=["GET", "POST"])
async def do_logout(request: Request):
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        await destroy_session(token)
    response = RedirectResponse("/login", status_code=302)
    response.delete_cookie(SESSION_COOKIE)
    return response


# ── Page routes ─────────────────────────────────────────────────
@app.get("/")
async def serve_landing():
    return FileResponse(os.path.join(LANDING_DIR, "index.html"))


@app.get("/submit")
async def serve_frontend():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


@app.get("/ops")
async def serve_monitor():
    return FileResponse(os.path.join(MONITOR_DIR, "index.html"))


@app.get("/results")
async def serve_results():
    return FileResponse(os.path.join(RESULTS_DIR, "index.html"))


@app.get("/my-jobs")
async def serve_my_jobs():
    return FileResponse(os.path.join(MYJOBS_DIR, "index.html"))


@app.get("/worker-logs")
async def serve_worker_logs():
    return FileResponse(os.path.join(WORKER_LOGS_DIR, "index.html"))




@app.get("/health")
async def health():
    """Health check — also verifies DB connection."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.fetchval("SELECT 1")
    return {"status": "ok", "db": "connected"}


@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """Serve branded 404 page for unknown routes."""
    # Return JSON for API requests
    if request.url.path.startswith("/api/") or request.url.path.startswith("/monitor/"):
        return JSONResponse({"detail": "Not found"}, status_code=404)
    return FileResponse(os.path.join(ERROR_DIR, "404.html"), status_code=404)


@app.get("/stats")
async def platform_stats():
    """Cumulative platform stats for the landing page — all-time counts."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        total_jobs = await conn.fetchval("SELECT COUNT(*) FROM jobs") or 0
        completed_jobs = await conn.fetchval("SELECT COUNT(*) FROM jobs WHERE status = 'completed'") or 0
        total_tasks = await conn.fetchval("SELECT COUNT(*) FROM job_tasks") or 0
        completed_tasks = await conn.fetchval("SELECT COUNT(*) FROM job_tasks WHERE status = 'submitted'") or 0
        total_workers = await conn.fetchval("SELECT COUNT(*) FROM worker_nodes") or 0
    return {
        "total_jobs": total_jobs,
        "completed_jobs": completed_jobs,
        "total_tasks": total_tasks,
        "completed_tasks": completed_tasks,
        "total_workers": total_workers,
    }
