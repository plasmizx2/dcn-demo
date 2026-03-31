import logging
import os
import asyncio
import httpx
from urllib.parse import urlencode
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse, JSONResponse
from contextlib import asynccontextmanager
from database import get_pool, close_pool
from apis.jobs import router as jobs_router
from apis.monitor import router as monitor_router
from apis.workers import router as workers_router
from auth import (
    find_or_create_oauth_user, create_session, get_session, destroy_session,
    update_user_role, list_users,
    SESSION_COOKIE, ADMIN_PAGES, ADMIN_API_PREFIXES, AUTH_REQUIRED_PAGES, PUBLIC_PREFIXES, ELEVATED_ROLES,
)
from config import (
    MAINTENANCE_INTERVAL_SECONDS, STALE_TASK_TIMEOUT_MINUTES,
    WORKER_PRUNE_TIMEOUT_MINUTES, SESSION_MAX_AGE_SECONDS,
)

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET", "")
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")

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
        # Migrate old password-based dcn_users to OAuth schema
        has_old = await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='dcn_users' AND column_name='password_hash')"
        )
        if has_old:
            logger.info("Migrating old dcn_users table to OAuth schema...")
            await conn.execute("DROP TABLE IF EXISTS sessions CASCADE")
            await conn.execute("DROP TABLE IF EXISTS dcn_users CASCADE")

        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS llm_cache (
                prompt_hash         TEXT PRIMARY KEY,
                response_text       TEXT NOT NULL,
                created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS dcn_users (
                id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                email               TEXT UNIQUE NOT NULL,
                name                TEXT,
                avatar_url          TEXT,
                provider            TEXT NOT NULL,
                provider_id         TEXT NOT NULL,
                role                TEXT NOT NULL DEFAULT 'customer',
                created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                UNIQUE(provider, provider_id)
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token_id            TEXT PRIMARY KEY,
                user_id             UUID NOT NULL REFERENCES dcn_users(id) ON DELETE CASCADE,
                created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            """
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

    # Auth-required pages → redirect to login if not signed in
    if path in AUTH_REQUIRED_PAGES:
        user = await get_session(request)
        if not user:
            return RedirectResponse("/login", status_code=302)

    # Admin-only pages → redirect to login if not admin/ceo
    if path in ADMIN_PAGES:
        user = await get_session(request)
        if not user:
            return RedirectResponse("/login", status_code=302)
        if user["role"] not in ELEVATED_ROLES:
            return RedirectResponse("/login", status_code=302)

    # Admin-only API routes → 401 JSON if not admin/ceo
    if any(path.startswith(p) for p in ADMIN_API_PREFIXES):
        user = await get_session(request)
        if not user or user["role"] not in ELEVATED_ROLES:
            return JSONResponse({"detail": "Admin access required"}, status_code=401)

    return await call_next(request)


# ── Auth routes ─────────────────────────────────────────────────

async def _finish_oauth_login(user: dict) -> RedirectResponse:
    """Shared helper: create session, set cookie, redirect."""
    token = await create_session(user)
    redirect = "/ops" if user["role"] in ELEVATED_ROLES else "/submit"
    response = RedirectResponse(redirect, status_code=302)
    response.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="lax", max_age=SESSION_MAX_AGE_SECONDS)
    return response


@app.get("/login")
async def serve_login(request: Request):
    user = await get_session(request)
    if user:
        return RedirectResponse("/ops" if user["role"] in ELEVATED_ROLES else "/submit")
    return FileResponse(os.path.join(LOGIN_DIR, "index.html"))


# ── Google OAuth ─────────────────────────────────────────────
@app.get("/auth/google")
async def google_login():
    params = urlencode({
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": f"{BASE_URL}/auth/google/callback",
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "select_account",
    })
    return RedirectResponse(f"https://accounts.google.com/o/oauth2/v2/auth?{params}")


@app.get("/auth/google/callback")
async def google_callback(request: Request):
    code = request.query_params.get("code")
    if not code:
        return RedirectResponse("/login")

    async with httpx.AsyncClient() as client:
        token_resp = await client.post("https://oauth2.googleapis.com/token", data={
            "code": code,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri": f"{BASE_URL}/auth/google/callback",
            "grant_type": "authorization_code",
        })
        if token_resp.status_code != 200:
            logger.error("Google token exchange failed: %s", token_resp.text)
            return RedirectResponse("/login")

        tokens = token_resp.json()
        userinfo_resp = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        if userinfo_resp.status_code != 200:
            logger.error("Google userinfo failed: %s", userinfo_resp.text)
            return RedirectResponse("/login")

        info = userinfo_resp.json()

    user = await find_or_create_oauth_user(
        email=info["email"],
        name=info.get("name"),
        avatar_url=info.get("picture"),
        provider="google",
        provider_id=str(info["id"]),
    )
    return await _finish_oauth_login(user)


# ── GitHub OAuth ─────────────────────────────────────────────
@app.get("/auth/github")
async def github_login():
    params = urlencode({
        "client_id": GITHUB_CLIENT_ID,
        "redirect_uri": f"{BASE_URL}/auth/github/callback",
        "scope": "read:user user:email",
    })
    return RedirectResponse(f"https://github.com/login/oauth/authorize?{params}")


@app.get("/auth/github/callback")
async def github_callback(request: Request):
    code = request.query_params.get("code")
    if not code:
        return RedirectResponse("/login")

    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            "https://github.com/login/oauth/access_token",
            data={
                "client_id": GITHUB_CLIENT_ID,
                "client_secret": GITHUB_CLIENT_SECRET,
                "code": code,
                "redirect_uri": f"{BASE_URL}/auth/github/callback",
            },
            headers={"Accept": "application/json"},
        )
        if token_resp.status_code != 200:
            logger.error("GitHub token exchange failed: %s", token_resp.text)
            return RedirectResponse("/login")

        tokens = token_resp.json()
        access_token = tokens.get("access_token")
        if not access_token:
            logger.error("GitHub no access_token: %s", tokens)
            return RedirectResponse("/login")

        headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
        user_resp = await client.get("https://api.github.com/user", headers=headers)
        if user_resp.status_code != 200:
            logger.error("GitHub user API failed: %s", user_resp.text)
            return RedirectResponse("/login")
        gh_user = user_resp.json()

        email = gh_user.get("email")
        if not email:
            emails_resp = await client.get("https://api.github.com/user/emails", headers=headers)
            if emails_resp.status_code == 200:
                for e in emails_resp.json():
                    if e.get("primary"):
                        email = e["email"]
                        break
        if not email:
            logger.error("GitHub: could not get user email")
            return RedirectResponse("/login")

    user = await find_or_create_oauth_user(
        email=email,
        name=gh_user.get("name") or gh_user.get("login"),
        avatar_url=gh_user.get("avatar_url"),
        provider="github",
        provider_id=str(gh_user["id"]),
    )
    return await _finish_oauth_login(user)


# ── Session endpoints ────────────────────────────────────────
@app.get("/auth/me")
async def auth_me(request: Request):
    user = await get_session(request)
    if not user:
        return JSONResponse({"detail": "Not logged in"}, status_code=401)
    return {
        "email": user["email"],
        "name": user.get("name") or user["email"].split("@")[0],
        "avatar_url": user.get("avatar_url"),
        "role": user["role"],
    }


@app.api_route("/auth/logout", methods=["GET", "POST"])
async def do_logout(request: Request):
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        await destroy_session(token)
    response = RedirectResponse("/login", status_code=302)
    response.delete_cookie(SESSION_COOKIE, path="/", samesite="lax")
    return response


# ── CEO user management ──────────────────────────────────────
@app.get("/auth/users")
async def get_users(request: Request):
    user = await get_session(request)
    if not user or user["role"] != "ceo":
        return JSONResponse({"detail": "CEO access required"}, status_code=403)
    users = await list_users()
    return users


@app.post("/auth/role")
async def change_role(request: Request):
    user = await get_session(request)
    if not user or user["role"] != "ceo":
        return JSONResponse({"detail": "CEO access required"}, status_code=403)
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"detail": "Invalid JSON"}, status_code=400)
    target_id = body.get("user_id")
    new_role = body.get("role")
    if not target_id or not new_role:
        return JSONResponse({"detail": "user_id and role required"}, status_code=400)
    if target_id == user["id"]:
        return JSONResponse({"detail": "Cannot change your own role"}, status_code=400)
    success = await update_user_role(target_id, new_role)
    if not success:
        return JSONResponse({"detail": "Failed — invalid role or user is CEO"}, status_code=400)
    return {"ok": True}


# ── Page routes ─────────────────────────────────────────────────
@app.get("/")
async def serve_landing():
    return FileResponse(os.path.join(LANDING_DIR, "index.html"))


@app.get("/submit")
async def serve_frontend():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


@app.get("/ops")
async def serve_monitor():
    response = FileResponse(os.path.join(MONITOR_DIR, "index.html"))
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    return response


@app.get("/results")
async def serve_results():
    response = FileResponse(os.path.join(RESULTS_DIR, "index.html"))
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    return response


@app.get("/my-jobs")
async def serve_my_jobs():
    response = FileResponse(os.path.join(MYJOBS_DIR, "index.html"))
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    return response


@app.get("/worker-logs")
async def serve_worker_logs():
    response = FileResponse(os.path.join(WORKER_LOGS_DIR, "index.html"))
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    return response




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
