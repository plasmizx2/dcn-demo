"""
Demo auth — cookie-based login with JSON user store.

TO UPGRADE TO REAL AUTH:
  1. Replace users.json with a DB table (hashed passwords via bcrypt)
  2. Swap verify_user() to query the DB instead of reading JSON
  3. Replace _sessions dict with Redis or DB-backed sessions (or switch to JWT)
  4. Add registration, password reset, etc.
  The middleware, role checks, and cookie handling stay the same.

CURRENT DEMO CREDENTIALS (in users.json):
  admin    / admin123    → role: admin  (can access /ops, /results, /monitor API)
  customer / customer123 → role: customer (can access / only)
"""

import os
import json
import secrets
import hashlib
from fastapi import Request, HTTPException
from fastapi.responses import RedirectResponse

USERS_FILE = os.path.join(os.path.dirname(__file__), "users.json")
SESSION_COOKIE = "dcn_session"

# In-memory session store: {token: {"username": ..., "role": ...}}
# Replace with Redis/DB for production.
_sessions: dict[str, dict] = {}


def load_users() -> dict:
    """Load users from JSON file. Replace with DB lookup later."""
    with open(USERS_FILE, "r") as f:
        return json.load(f)


def verify_user(username: str, password: str) -> dict | None:
    """Check credentials. Returns user dict or None. Replace with hashed passwords later."""
    users = load_users()
    user = users.get(username)
    if user and user["password"] == password:
        return {"username": username, "role": user["role"], "name": user.get("name", username)}
    return None


def create_session(user: dict) -> str:
    """Create a session token for an authenticated user."""
    token = secrets.token_hex(32)
    _sessions[token] = user
    return token


def get_session(request: Request) -> dict | None:
    """Get the current user from session cookie."""
    token = request.cookies.get(SESSION_COOKIE)
    if token and token in _sessions:
        return _sessions[token]
    return None


def destroy_session(token: str):
    """Remove a session."""
    _sessions.pop(token, None)


def require_role(request: Request, role: str):
    """Check that the current user has the required role."""
    user = get_session(request)
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
