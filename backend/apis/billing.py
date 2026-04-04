"""
Billing API router for DCN.

Endpoints:
  GET  /billing/config                  — publishable key + enabled flag (public)
  POST /billing/create-payment-intent   — create PaymentIntent for a job estimate
  GET  /billing/payment-status/{pi_id}  — check PaymentIntent status
  GET  /billing/tier                    — current user's tier
  POST /billing/upgrade                 — change tier (free/paygo/pro)
  POST /billing/connect/onboard         — start Stripe Connect onboarding for worker
  GET  /billing/connect/status          — worker's Connect account status
  GET  /billing/payouts                 — payout history for the current user
  POST /billing/webhooks                — Stripe webhook handler (Stripe-signed)
  GET  /billing/admin/payments          — admin payment list
  GET  /billing/admin/payouts           — admin payout list
"""
import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from database import get_pool
from auth import get_session, ELEVATED_ROLES
import billing

router = APIRouter(prefix="/billing")
logger = logging.getLogger("dcn.billing")


# ── Schemas ──────────────────────────────────────────────────

class UpgradeTierRequest(BaseModel):
    tier: str  # "free", "paygo", "pro"


# ── Public config ────────────────────────────────────────────

@router.get("/config")
async def get_billing_config() -> dict:
    """Return the Stripe publishable key and whether billing is active. Public endpoint."""
    return {
        "enabled": billing.is_enabled(),
        "publishable_key": billing.STRIPE_PUBLISHABLE_KEY if billing.is_enabled() else None,
        "pro_price_monthly": 5.00,
    }


# ── Payment Intents ──────────────────────────────────────────

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


# ── Tier management ──────────────────────────────────────────

@router.get("/tier")
async def get_user_tier(request: Request):
    """Return the authenticated user's current tier."""
    user = await get_session(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT tier, stripe_customer_id, stripe_subscription_id, balance_cents FROM dcn_users WHERE id = $1::uuid",
            user["id"],
        )
    if not row:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "tier": row["tier"],
        "has_payment_method": bool(row["stripe_customer_id"]),
        "has_subscription": bool(row["stripe_subscription_id"]),
        "balance_cents": row["balance_cents"] or 0,
    }


@router.post("/upgrade")
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
        if not billing.is_enabled():
            raise HTTPException(status_code=503, detail="Billing not configured")
        try:
            result = await billing.create_pro_subscription(user["id"], user["email"])
            return result
        except ValueError as e:
            raise HTTPException(status_code=500, detail=str(e)) from e
        except Exception as e:
            logger.error("Pro upgrade failed for user %s: %s", user["id"], e, exc_info=True)
            raise HTTPException(status_code=500, detail=str(e)) from e

    if tier == "paygo":
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE dcn_users SET tier = 'paygo' WHERE id = $1::uuid",
                user["id"],
            )
        return {"tier": "paygo"}

    if tier == "free":
        async with pool.acquire() as conn:
            sub_id = await conn.fetchval(
                "SELECT stripe_subscription_id FROM dcn_users WHERE id = $1::uuid",
                user["id"],
            )
        if sub_id:
            await billing.cancel_pro_subscription(user["id"])
        else:
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE dcn_users SET tier = 'free' WHERE id = $1::uuid",
                    user["id"],
                )
        return {"tier": "free"}


# ── Balance / Top-up ────────────────────────────────────────

@router.post("/topup")
async def create_topup(request: Request) -> dict:
    """Create a Stripe Checkout session to top up balance."""
    if not billing.is_enabled():
        raise HTTPException(status_code=503, detail="Billing not configured")
    user = await get_session(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    amount_cents = int(body.get("amount_cents", 0))
    if amount_cents < 500:
        raise HTTPException(status_code=400, detail="Minimum top-up is $5.00")
    try:
        result = await billing.create_topup_checkout_session(user["id"], user["email"], amount_cents)
        return result
    except Exception as e:
        logger.error("Top-up failed for user %s: %s", user["id"], e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/verify-pro")
async def verify_pro(request: Request) -> dict:
    """Verify a Pro subscription Checkout session and activate tier."""
    user = await get_session(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    if not billing.is_enabled():
        raise HTTPException(status_code=503, detail="Billing not configured")
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    session_id = body.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id required")
    try:
        result = await billing.verify_and_activate_pro(session_id, str(user["id"]))
        return result
    except Exception as e:
        logger.error("verify-pro failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/verify-topup")
async def verify_topup(request: Request) -> dict:
    """Verify a completed Stripe Checkout session and credit balance."""
    user = await get_session(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    if not billing.is_enabled():
        raise HTTPException(status_code=503, detail="Billing not configured")
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    session_id = body.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id required")
    try:
        result = await billing.verify_and_credit_topup(session_id, str(user["id"]))
        return result
    except Exception as e:
        logger.error("verify-topup failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/balance")
async def get_balance(request: Request) -> dict:
    """Return the authenticated user's current balance."""
    user = await get_session(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    pool = await get_pool()
    async with pool.acquire() as conn:
        balance = await conn.fetchval(
            "SELECT balance_cents FROM dcn_users WHERE id = $1::uuid", user["id"]
        )
    cents = balance or 0
    return {"balance_cents": cents, "balance_dollars": round(cents / 100, 2)}


@router.get("/balance/history")
async def get_balance_history(request: Request) -> list[dict]:
    """Return recent balance transactions for the authenticated user."""
    user = await get_session(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT id, amount_cents, balance_after, tx_type, reference_id, description, created_at
               FROM balance_transactions WHERE user_id = $1::uuid
               ORDER BY created_at DESC LIMIT 50""",
            user["id"],
        )
    return [dict(r) for r in rows]


# ── Stripe Connect (worker payouts) ─────────────────────────

@router.post("/connect/onboard")
async def start_connect_onboarding(request: Request) -> dict:
    """
    Create (or look up) a Stripe Express account for the current user
    and return a one-time onboarding link.
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

    base_url = str(body.get("base_url", billing.BASE_URL)).rstrip("/")

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
    """Return the current user's Stripe Connect status."""
    if not billing.is_enabled():
        return {"connected": False, "reason": "billing_not_configured"}

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
        return {"connected": False, "account_id": None, "status": "none"}

    if row["status"] == "active":
        return {"connected": True, "account_id": row["stripe_account_id"], "status": "active"}

    try:
        acct = billing.retrieve_account(row["stripe_account_id"])
        return {"connected": acct["payouts_enabled"], "account_id": row["stripe_account_id"], **acct}
    except Exception:
        return {"connected": False, "account_id": row["stripe_account_id"], "status": row["status"]}


@router.get("/payouts")
async def list_my_payouts(request: Request) -> list[dict]:
    """Return payout history for the authenticated user."""
    user = await get_session(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT p.id, p.job_id, p.amount_cents, p.status, p.payment_type, p.created_at,
                   j.title AS job_title
            FROM payments p
            LEFT JOIN jobs j ON j.id = p.job_id
            WHERE p.user_id = $1::uuid
            ORDER BY p.created_at DESC
            LIMIT 50
            """,
            user["id"],
        )
    return [dict(r) for r in rows]


# ── Admin endpoints ──────────────────────────────────────────

@router.get("/admin/payments")
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


@router.get("/admin/payouts")
async def admin_list_payouts(request: Request):
    """Admin-only: list worker payouts."""
    user = await get_session(request)
    if not user or user.get("role") not in ELEVATED_ROLES:
        raise HTTPException(status_code=403, detail="Admin access required")

    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM payments
            WHERE payment_type = 'payout'
            ORDER BY created_at DESC
            LIMIT 100
            """
        )
    return [dict(r) for r in rows]


# ── Webhooks ─────────────────────────────────────────────────

@router.post("/webhooks")
async def stripe_webhook(request: Request):
    """Stripe webhook endpoint — verifies signature and processes events."""
    print(f"[WEBHOOK] Received POST /billing/webhooks", flush=True)
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")

    if not billing.STRIPE_WEBHOOK_SECRET:
        print("[WEBHOOK] ERROR: STRIPE_WEBHOOK_SECRET not set", flush=True)
        raise HTTPException(status_code=500, detail="Webhook secret not configured")

    try:
        event = billing.construct_webhook_event(payload, sig)
        print(f"[WEBHOOK] Signature OK, event type: {event.type}", flush=True)
    except Exception as e:
        print(f"[WEBHOOK] Signature FAILED: {e}", flush=True)
        raise HTTPException(status_code=400, detail="Invalid signature")

    try:
        print(f"[WEBHOOK] Handling event: {event.type}", flush=True)
        await billing.handle_webhook_event(event)
        print(f"[WEBHOOK] Event handled OK", flush=True)
    except Exception as e:
        print(f"[WEBHOOK] Event processing FAILED: {e}", flush=True)
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail="Event processing failed") from e
    return {"received": True}
