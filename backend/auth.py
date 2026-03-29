"""
DCN auth (demo-grade):

- Cookie-based sessions backed by PostgreSQL (`sessions` table)
- Users stored in PostgreSQL (`dcn_users` table)
- Simple SHA-256 password hashing (sufficient for demo; not recommended for production)

Default seeded users (created at startup if `dcn_users` is empty):
  admin    / admin123    → role: admin
  customer / customer123 → role: customer
"""

import os
import json
import secrets
import hashlib
import logging
from fastapi import Request, HTTPException
from fastapi.responses import RedirectResponse

from database import get_pool

logger = logging.getLogger("dcn.auth")
SESSION_COOKIE = "dcn_session"

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


async def verify_user(username: str, password: str) -> dict | None:
    """Check credentials against PostgreSQL. Returns user dict or None."""
    pool = await get_pool()
    pwd_hash = hash_password(password)
    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT id, username, role FROM dcn_users WHERE username = $1 AND password_hash = $2",
            username, pwd_hash
        )
        if user:
            return {"id": str(user["id"]), "username": user["username"], "role": user["role"], "name": user["username"]}
    return None


async def create_session(user: dict) -> str:
    """Create a high-entropy session token and bind it in PostgreSQL."""
    pool = await get_pool()
    token = secrets.token_hex(32)
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO sessions (token_id, user_id) VALUES ($1, $2)",
            token, user["id"]
        )
    return token


async def get_session(request: Request) -> dict | None:
    """Validate token against DB and return user."""
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT u.id, u.username, u.role 
            FROM sessions s
            JOIN dcn_users u ON s.user_id = u.id
            WHERE s.token_id = $1
            """,
            token
        )
        if row:
            return {"id": str(row["id"]), "username": row["username"], "role": row["role"], "name": row["username"]}
    return None


async def destroy_session(token: str):
    """Delete session from Postgres."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM sessions WHERE token_id = $1", token)


async def require_role(request: Request, role: str):
    """Check that the current user has the required role."""
    user = await get_session(request)
    if not user:
        return None
    if user["role"] != role:
        return None
    return user


# Pages that require admin role
ADMIN_PAGES = {"/ops", "/results", "/worker-logs"}
# API routes that require admin role
ADMIN_API_PREFIXES = ["/monitor/"]
# Prefixes that don't need auth (worker endpoints, public pages, jobs API)
PUBLIC_PREFIXES = ["/login", "/health", "/submit", "/workers/", "/tasks/", "/jobs", "/auth/", "/stats", "/my-jobs"]
