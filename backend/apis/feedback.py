"""API routes for bug reports and contact messages."""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, field_validator
import re
from typing import Optional
from database import get_pool
from auth import get_session, ELEVATED_ROLES
from rate_limit import check_rate_limit

router = APIRouter()


class BugReport(BaseModel):
    subject: str
    description: str
    page_url: Optional[str] = None


class ContactMessage(BaseModel):
    name: str
    email: str
    subject: str = "general"
    message: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        pattern = r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
        if not re.match(pattern, v.strip()):
            raise ValueError("Invalid email address")
        return v.strip()


@router.post("/bugs")
async def create_bug_report(body: BugReport, request: Request) -> dict:
    """Submit a bug report. Requires authentication."""
    check_rate_limit(request, max_requests=5, window_seconds=60)  # 5 reports/min
    user = await get_session(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    if not body.subject.strip() or not body.description.strip():
        raise HTTPException(status_code=400, detail="Subject and description are required")

    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO bug_reports (user_id, subject, description, page_url)
            VALUES ($1::uuid, $2, $3, $4)
            RETURNING id, created_at
            """,
            user["id"],
            body.subject.strip(),
            body.description.strip(),
            body.page_url or None,
        )
    return {"id": str(row["id"]), "created_at": str(row["created_at"])}


@router.get("/bugs")
async def list_bug_reports(request: Request) -> list[dict]:
    """List all bug reports. Admin/CEO only."""
    user = await get_session(request)
    if not user or user.get("role") not in ELEVATED_ROLES:
        raise HTTPException(status_code=403, detail="Admin access required")

    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT b.*, u.email AS reporter_email, u.name AS reporter_name
            FROM bug_reports b
            LEFT JOIN dcn_users u ON u.id = b.user_id
            ORDER BY b.created_at DESC
            """
        )
    return [dict(r) for r in rows]


@router.post("/contact")
async def create_contact_message(body: ContactMessage, request: Request) -> dict:
    """Submit a contact message. Works for both authenticated and anonymous users."""
    check_rate_limit(request, max_requests=3, window_seconds=60)  # 3 messages/min
    if not body.name.strip() or not body.email.strip() or not body.message.strip():
        raise HTTPException(status_code=400, detail="Name, email, and message are required")

    user = await get_session(request)
    user_id = user["id"] if user else None

    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO contact_messages (user_id, name, email, subject, message)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id, created_at
            """,
            user_id,
            body.name.strip(),
            body.email.strip(),
            body.subject,
            body.message.strip(),
        )
    return {"id": str(row["id"]), "created_at": str(row["created_at"])}


@router.get("/contact/messages")
async def list_contact_messages(request: Request) -> list[dict]:
    """List all contact messages. Admin/CEO only."""
    user = await get_session(request)
    if not user or user.get("role") not in ELEVATED_ROLES:
        raise HTTPException(status_code=403, detail="Admin access required")

    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM contact_messages ORDER BY created_at DESC"
        )
    return [dict(r) for r in rows]
