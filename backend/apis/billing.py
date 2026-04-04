"""
Billing API router for DCN.

Endpoints:
  GET  /billing/config                  — publishable key + enabled flag (public)
  POST /billing/create-payment-intent   — create PaymentIntent for a job estimate
  GET  /billing/payment-status/{pi_id} — check PaymentIntent status
  POST /billing/connect/onboard         — start Stripe Connect onboarding for worker
  GET  /billing/connect/status          — worker's Connect account status
  GET  /billing/payouts                 — payout history for the current user
  POST /billing/webhooks                — Stripe webhook handler (Stripe-signed)
"""
import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from database import get_pool
from auth import get_session
import billing

router = APIRouter(prefix="/billing")
logger = logging.getLogger("dcn.billing")


@router.get("/config")
async def get_billing_config() -> dict:
    """Return the Stripe publishable key and whether billing is active. Public endpoint."""
    return {
        "enabled": billing.is_enabled(),
        "publishable_key": billing.STRIPE_PUBLISHABLE_KEY if billing.is_enabled() else None,
    }


@router.post("/create-payment-intent")
async def create_payment_intent(request: Request) -> dict:
    """
    Create a Stripe PaymentIntent for a job submission.

    Body: { amount: float (dollars), job_title: str }
    Returns: { client_secret, payment_intent_id, amount_cents }
    """
    if not billing.is_enabled():
        raise HTTPException(status_code=503, detail="Billing not configured")

    user = await get_session(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    amount_dollars = float(body.get("amount", 0))
    if amount_dollars <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")

    job_title = str(body.get("job_title", "DCN Job"))[:255]
    amount_cents = billing.dollars_to_cents(amount_dollars)

    try:
        result = billing.create_payment_intent(
            amount_cents=amount_cents,
            metadata={
                "user_id": user["id"],
                "user_email": user["email"],
                "job_title": job_title,
            },
        )
    except Exception as exc:
        logger.error("Failed to create PaymentIntent: %s", exc)
        raise HTTPException(status_code=502, detail="Payment service unavailable")

    return {
        "client_secret": result["client_secret"],
        "payment_intent_id": result["payment_intent_id"],
        "amount_cents": amount_cents,
    }


@router.get("/payment-status/{pi_id}")
async def get_payment_status(pi_id: str, request: Request) -> dict:
    """Return the current status of a PaymentIntent."""
    if not billing.is_enabled():
        raise HTTPException(status_code=503, detail="Billing not configured")

    user = await get_session(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        return billing.retrieve_payment_intent(pi_id)
    except Exception as exc:
        logger.error("Failed to retrieve PaymentIntent %s: %s", pi_id, exc)
        raise HTTPException(status_code=502, detail="Payment service unavailable")


@router.post("/connect/onboard")
async def start_connect_onboarding(request: Request) -> dict:
    """
    Create (or look up) a Stripe Express account for the current user
    and return a one-time onboarding link.

    Body (optional): { base_url: str }
    Returns: { onboarding_url, stripe_account_id }
    """
    if not billing.is_enabled():
        raise HTTPException(status_code=503, detail="Billing not configured")

    user = await get_session(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        body = await request.json()
    except Exception:
        body = {}

    base_url = str(body.get("base_url", "http://localhost:8000")).rstrip("/")

    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT stripe_account_id FROM stripe_accounts WHERE user_id = $1::uuid",
            user["id"],
        )

    if row and row["stripe_account_id"]:
        stripe_account_id = row["stripe_account_id"]
    else:
        try:
            stripe_account_id = billing.create_connect_account(user["email"])
        except Exception as exc:
            logger.error("Failed to create Connect account for %s: %s", user["email"], exc)
            raise HTTPException(status_code=502, detail="Payment service unavailable")

        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO stripe_accounts (user_id, stripe_account_id, status)
                VALUES ($1::uuid, $2, 'pending')
                ON CONFLICT (user_id) DO UPDATE
                  SET stripe_account_id = EXCLUDED.stripe_account_id,
                      status = 'pending',
                      updated_at = NOW()
                """,
                user["id"],
                stripe_account_id,
            )

    try:
        link_url = billing.create_onboarding_link(
            account_id=stripe_account_id,
            return_url=f"{base_url}/worker/stripe?onboarding=complete",
            refresh_url=f"{base_url}/worker/stripe?onboarding=refresh",
        )
    except Exception as exc:
        logger.error("Failed to create onboarding link for account %s: %s", stripe_account_id, exc)
        raise HTTPException(status_code=502, detail="Payment service unavailable")

    return {"onboarding_url": link_url, "stripe_account_id": stripe_account_id}


@router.get("/connect/status")
async def get_connect_status(request: Request) -> dict:
    """Return the Stripe Connect account status for the current user."""
    if not billing.is_enabled():
        return {"enabled": False}

    user = await get_session(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT stripe_account_id, status FROM stripe_accounts WHERE user_id = $1::uuid",
            user["id"],
        )

    if not row:
        return {"connected": False}

    try:
        account = billing.retrieve_account(row["stripe_account_id"])
    except Exception as exc:
        logger.warning("Could not retrieve account %s: %s", row["stripe_account_id"], exc)
        return {
            "connected": True,
            "stripe_account_id": row["stripe_account_id"],
            "status": row["status"],
            "details": None,
        }

    new_status = (
        "active" if account["payouts_enabled"]
        else ("pending" if account["details_submitted"] else "incomplete")
    )
    if new_status != row["status"]:
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE stripe_accounts SET status = $1, updated_at = NOW() WHERE user_id = $2::uuid",
                new_status,
                user["id"],
            )

    return {
        "connected": True,
        "stripe_account_id": row["stripe_account_id"],
        "status": new_status,
        "payouts_enabled": account["payouts_enabled"],
        "details_submitted": account["details_submitted"],
    }


@router.get("/payouts")
async def list_payouts(request: Request) -> list[dict]:
    """Return payment / payout history for the current user (newest first)."""
    user = await get_session(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, job_id, stripe_id, amount_cents, status, payment_type, created_at
            FROM payments
            WHERE user_id = $1::uuid
            ORDER BY created_at DESC
            LIMIT 100
            """,
            user["id"],
        )
    return [dict(r) for r in rows]


@router.post("/webhooks")
async def stripe_webhook(request: Request):
    """
    Handle incoming Stripe webhook events.

    Verified via Stripe-Signature header — no user session required.
    """
    if not billing.is_enabled():
        return JSONResponse({"status": "billing_disabled"})

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        event = billing.construct_webhook_event(payload, sig_header)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except Exception as exc:
        logger.error("Webhook signature verification failed: %s", exc)
        raise HTTPException(status_code=400, detail="Invalid signature")

    event_type: str = event["type"]
    data = event["data"]["object"]
    pool = await get_pool()

    if event_type == "payment_intent.succeeded":
        pi_id: str = data["id"]
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE payments SET status = 'succeeded' WHERE stripe_id = $1",
                pi_id,
            )
        logger.info("PaymentIntent succeeded: %s", pi_id)

    elif event_type == "payment_intent.payment_failed":
        pi_id = data["id"]
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE payments SET status = 'failed' WHERE stripe_id = $1",
                pi_id,
            )
        logger.warning("PaymentIntent failed: %s", pi_id)

    elif event_type == "account.updated":
        account_id: str = data["id"]
        payouts_enabled: bool = data.get("payouts_enabled", False)
        details_submitted: bool = data.get("details_submitted", False)
        new_status = (
            "active" if payouts_enabled
            else ("pending" if details_submitted else "incomplete")
        )
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE stripe_accounts SET status = $1, updated_at = NOW() WHERE stripe_account_id = $2",
                new_status,
                account_id,
            )
        logger.info("Connect account updated: %s → %s", account_id, new_status)

    elif event_type == "transfer.created":
        logger.info("Transfer created: %s", data.get("id"))

    return JSONResponse({"status": "ok"})
