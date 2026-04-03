"""Simple in-memory rate limiter for FastAPI.

Uses a sliding window per key (IP or user ID). No external dependencies.
Thread-safe via asyncio (single event loop).

Limits reset naturally as old entries expire — no background cleanup needed
because we prune on each check.
"""

import time
from collections import defaultdict
from fastapi import Request, HTTPException


# Store: key → list of timestamps
_buckets: dict[str, list[float]] = defaultdict(list)


def _get_client_key(request: Request) -> str:
    """Best-effort client identifier: user ID if authenticated, else IP."""
    # Check if auth already attached a user (set by middleware)
    user = getattr(request.state, "user", None)
    if user and isinstance(user, dict) and user.get("id"):
        return f"user:{user['id']}"
    # Fall back to IP
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return f"ip:{forwarded.split(',')[0].strip()}"
    client = request.client
    return f"ip:{client.host}" if client else "ip:unknown"


def check_rate_limit(request: Request, max_requests: int, window_seconds: int):
    """Raise 429 if client exceeds max_requests within the sliding window.

    Call this at the top of any endpoint you want to protect.
    """
    key = _get_client_key(request)
    now = time.monotonic()
    cutoff = now - window_seconds

    # Prune expired entries
    bucket = _buckets[key]
    _buckets[key] = bucket = [t for t in bucket if t > cutoff]

    if len(bucket) >= max_requests:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Max {max_requests} requests per {window_seconds}s.",
        )

    bucket.append(now)
