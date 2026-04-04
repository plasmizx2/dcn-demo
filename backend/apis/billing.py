"""
Billing API routes — Stripe payments, subscriptions, Connect, webhooks.
"""

import logging
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional

import stripe

from auth import get_session, ELEVATED_ROLES
from database import get_pool
from billing import (
    STRIPE_PUBLISHABLE_KEY,
    STRIPE_WEBHOOK_SECRET,
    create_payment_intent,
    verify_payment_intent,
    create_pro_subscription,
    cancel_pro_subscription,
    create_worker_connect_link,
    get_worker_connect_status,
    handle_webhook_event,
    refund_payment,
    _dollars_to_cents,
)
from config import PLATFORM_FEE_PERCENT
from pricing import estimate_job_cost
from planner import plan_tasks

logger = logging.getLogger("dcn.billing")
router = APIRouter()


# ── Schemas ──────────────────────────────────────────────────

class CreatePaymentIntentRequest(BaseModel):
    task_type: str
    input_payload: dict = {}


class UpgradeTierRequest(BaseModel):
    tier: str  # "free", "paygo", "pro"


class ConnectOnboardRequest(BaseModel):
    worker_node_id: str


# ── Public config (publishable key for frontend) ─────────────

@router.get("/billing/config")
async def billing_config():
    """Return non-secret Stripe config for the frontend."""
    return {
        "publishable_key": STRIPE_PUBLISHABLE_KEY,
        "pro_price_monthly": 5.00,
    }


# ── Payment Intents ──────────────────────────────────────────

@router.post("/billing/create-payment-intent")
async def create_payment_intent_route(body: CreatePaymentIntentRequest, request: Request):
    """Create a PaymentIntent for a pay-as-you-go job. Frontend confirms with Stripe Elements."""
    user = await get_session(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    # Estimate cost from planner
    try:
        subtasks = plan_tasks(body.task_type, body.input_payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    est = estimate_job_cost(subtasks)
    amount_cents = _dollars_to_cents(est["estimated_total"])
    fee_cents = _dollars_to_cents(est["platform_fee"])

    if amount_cents < 50:
        raise HTTPException(status_code=400, detail="Amount too small for Stripe (minimum $0.50)")

    result = await create_payment_intent(
        user_id=user["id"],
        email=user["email"],
        amount_cents=amount_cents,
        platform_fee_cents=fee_cents,
    )
    result["estimated_cost"] = est
    return result


@router.get("/billing/payment-status/{payment_intent_id}")
async def payment_status(payment_intent_id: str, request: Request):
    """Check the status of a payment intent."""
    user = await get_session(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    row = await verify_payment_intent(payment_intent_id, user["id"])
    if not row:
        raise HTTPException(status_code=404, detail="Payment not found")
    return {"status": row["status"], "amount_cents": row["amount_cents"]}


# ── Tier management ──────────────────────────────────────────

@router.get("/billing/tier")
async def get_user_tier(request: Request):
    """Return the authenticated user's current tier."""
    user = await get_session(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT tier, stripe_customer_id, stripe_subscription_id FROM dcn_users WHERE id = $1::uuid",
            user["id"],
        )
    if not row:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "tier": row["tier"],
        "has_payment_method": bool(row["stripe_customer_id"]),
        "has_subscription": bool(row["stripe_subscription_id"]),
    }


@router.post("/billing/upgrade")
async def upgrade_tier(body: UpgradeTierRequest, request: Request):
    """Change the user's pricing tier."""
    user = await get_session(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    tier = body.tier.lower()
    if tier not in ("free", "paygo", "pro"):
        raise HTTPException(status_code=400, detail="Invalid tier. Must be free, paygo, or pro.")

    pool = await get_pool()

    if tier == "pro":
        # Create Stripe Checkout for subscription
        try:
            result = await create_pro_subscription(user["id"], user["email"])
            return result
        except ValueError as e:
            raise HTTPException(status_code=500, detail=str(e)) from e

    if tier == "paygo":
        # Just set tier — payment method will be added when they submit a job
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE dcn_users SET tier = 'paygo' WHERE id = $1::uuid",
                user["id"],
            )
        return {"tier": "paygo"}

    if tier == "free":
        # Downgrade — cancel subscription if active
        async with pool.acquire() as conn:
            sub_id = await conn.fetchval(
                "SELECT stripe_subscription_id FROM dcn_users WHERE id = $1::uuid",
                user["id"],
            )
        if sub_id:
            await cancel_pro_subscription(user["id"])
        else:
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE dcn_users SET tier = 'free' WHERE id = $1::uuid",
                    user["id"],
                )
        return {"tier": "free"}


# ── Stripe Connect (worker payouts) ─────────────────────────

@router.post("/billing/connect/onboard")
async def connect_onboard(body: ConnectOnboardRequest, request: Request):
    """Generate a Stripe Connect onboarding link for a worker node."""
    user = await get_session(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    if user.get("role") not in ELEVATED_ROLES:
        raise HTTPException(status_code=403, detail="Admin access required")

    try:
        url = await create_worker_connect_link(body.worker_node_id)
        return {"onboarding_url": url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/billing/connect/status/{worker_node_id}")
async def connect_status(worker_node_id: str, request: Request):
    """Check if a worker has completed Stripe Connect setup."""
    user = await get_session(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    return await get_worker_connect_status(worker_node_id)


# ── Admin: payment overview ──────────────────────────────────

@router.get("/billing/admin/payments")
async def admin_list_payments(request: Request):
    """Admin-only: list recent payments."""
    user = await get_session(request)
    if not user or user.get("role") not in ELEVATED_ROLES:
        raise HTTPException(status_code=403, detail="Admin access required")

    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT p.*, j.title AS job_title, u.email AS user_email
            FROM payments p
            LEFT JOIN jobs j ON j.id = p.job_id
            LEFT JOIN dcn_users u ON u.id = p.user_id
            ORDER BY p.created_at DESC
            LIMIT 100
            """
        )
    return [dict(r) for r in rows]


@router.get("/billing/admin/payouts")
async def admin_list_payouts(request: Request):
    """Admin-only: list worker payouts."""
    user = await get_session(request)
    if not user or user.get("role") not in ELEVATED_ROLES:
        raise HTTPException(status_code=403, detail="Admin access required")

    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM worker_payouts ORDER BY created_at DESC LIMIT 100"
        )
    return [dict(r) for r in rows]


# ── Webhooks ─────────────────────────────────────────────────

@router.post("/billing/webhooks")
async def stripe_webhook(request: Request):
    """Stripe webhook endpoint — verifies signature and processes events."""
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")

    if not STRIPE_WEBHOOK_SECRET:
        logger.warning("STRIPE_WEBHOOK_SECRET not set — skipping signature verification")
        event = stripe.Event.construct_from(
            stripe.util.convert_to_stripe_object(
                stripe.util.json.loads(payload)
            ),
            stripe.api_key,
        )
    else:
        try:
            event = stripe.Webhook.construct_event(payload, sig, STRIPE_WEBHOOK_SECRET)
        except stripe.SignatureVerificationError:
            raise HTTPException(status_code=400, detail="Invalid signature")

    await handle_webhook_event(event)
    return {"received": True}
