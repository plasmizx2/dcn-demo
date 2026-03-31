"""
DCN auth — OAuth-based (Google + GitHub).

- Cookie-based sessions backed by PostgreSQL (`sessions` table)
- Users created/looked-up via OAuth provider (no passwords stored)
- Role hierarchy: ceo > admin > customer
- CEO email set via CEO_EMAIL env var — auto-promoted on login
"""

import os
import secrets
import logging
from fastapi import Request

from database import get_pool

logger = logging.getLogger("dcn.auth")
SESSION_COOKIE = "dcn_session"
CEO_EMAIL = os.getenv("CEO_EMAIL", "").lower().strip()
ELEVATED_ROLES = {"ceo", "admin"}


async def find_or_create_oauth_user(
    email: str, name: str | None, avatar_url: str | None,
    provider: str, provider_id: str,
) -> dict:
    """Upsert an OAuth user. Returns user dict. Auto-assigns CEO role if email matches."""
    pool = await get_pool()
    role = "ceo" if email.lower() == CEO_EMAIL and CEO_EMAIL else "customer"

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, email, name, avatar_url, role FROM dcn_users WHERE provider = $1 AND provider_id = $2",
            provider, provider_id,
        )
        if row:
            if CEO_EMAIL and row["email"].lower() == CEO_EMAIL and row["role"] != "ceo":
                await conn.execute("UPDATE dcn_users SET role = 'ceo' WHERE id = $1", row["id"])
                row = dict(row)
                row["role"] = "ceo"

            await conn.execute(
                "UPDATE dcn_users SET name = $1, avatar_url = $2 WHERE id = $3",
                name or row["name"], avatar_url or row["avatar_url"], row["id"],
            )
            return {
                "id": str(row["id"]),
                "email": row["email"],
                "name": name or row["name"],
                "avatar_url": avatar_url or row["avatar_url"],
                "role": row["role"],
            }

        new_id = await conn.fetchval(
            """INSERT INTO dcn_users (email, name, avatar_url, provider, provider_id, role)
               VALUES ($1, $2, $3, $4, $5, $6)
               ON CONFLICT (email) DO UPDATE SET name = EXCLUDED.name, avatar_url = EXCLUDED.avatar_url,
                   provider = EXCLUDED.provider, provider_id = EXCLUDED.provider_id
               RETURNING id""",
            email.lower(), name, avatar_url, provider, provider_id, role,
        )
        return {
            "id": str(new_id),
            "email": email.lower(),
            "name": name,
            "avatar_url": avatar_url,
            "role": role,
        }


async def create_session(user: dict) -> str:
    """Create a high-entropy session token and bind it in PostgreSQL."""
    pool = await get_pool()
    token = secrets.token_hex(32)
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO sessions (token_id, user_id) VALUES ($1, $2)",
            token, user["id"],
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
            """SELECT u.id, u.email, u.name, u.avatar_url, u.role
               FROM sessions s
               JOIN dcn_users u ON s.user_id = u.id
               WHERE s.token_id = $1""",
            token,
        )
        if row:
            return {
                "id": str(row["id"]),
                "email": row["email"],
                "name": row["name"],
                "avatar_url": row["avatar_url"],
                "role": row["role"],
            }
    return None


async def destroy_session(token: str):
    """Delete session from Postgres."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM sessions WHERE token_id = $1", token)


async def update_user_role(user_id: str, new_role: str) -> bool:
    """CEO-only: change a user's role. Returns True on success."""
    if new_role not in ("admin", "customer"):
        return False
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE dcn_users SET role = $1 WHERE id = $2 AND role != 'ceo'",
            new_role, user_id,
        )
        return result != "UPDATE 0"


async def list_users() -> list[dict]:
    """Return all users for the CEO management panel."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, email, name, avatar_url, provider, role, created_at FROM dcn_users ORDER BY created_at",
        )
        return [
            {
                "id": str(r["id"]),
                "email": r["email"],
                "name": r["name"],
                "avatar_url": r["avatar_url"],
                "provider": r["provider"],
                "role": r["role"],
                "created_at": r["created_at"].isoformat(),
            }
            for r in rows
        ]


# Pages that require admin (or ceo) role
ADMIN_PAGES = {"/ops", "/results", "/worker-logs"}
# API routes that require admin (or ceo) role
ADMIN_API_PREFIXES = ["/monitor/"]
# Pages that require any authenticated user (non-admin)
AUTH_REQUIRED_PAGES = {"/submit"}
# Prefixes that don't need auth
PUBLIC_PREFIXES = [
    "/login", "/health", "/workers/", "/tasks/", "/jobs", "/auth/", "/stats", "/my-jobs", "/datasets",
]
