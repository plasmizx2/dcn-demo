"""
Stripe billing for DCN.

Handles:
- Payment Intents (authorize + capture) for job submitters
- Stripe Connect onboarding for worker payouts
- Transfers to workers after job completion
- Pro tier subscriptions ($5/mo)
- Refunds for failed/cancelled jobs
"""

import os
import logging
import math

import stripe

from database import get_pool
from pricing import calculate_actual_cost
from config import STRIPE_CURRENCY, PLATFORM_FEE_PERCENT

logger = logging.getLogger("dcn.billing")

# ── Stripe config ───────────────────────────────────────────
stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PRO_PRICE_ID = os.getenv("STRIPE_PRO_PRICE_ID", "")
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")


def _dollars_to_cents(amount: float) -> int:
    """Convert a dollar amount to integer cents, rounding up to nearest cent."""
    return max(0, math.ceil(amount * 100))


# ── Stripe Customer ─────────────────────────────────────────

async def get_or_create_stripe_customer(user_id: str, email: str) -> str:
    """Get or create a Stripe customer for a DCN user. Returns customer ID."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        existing = await conn.fetchval(
            "SELECT stripe_customer_id FROM dcn_users WHERE id = $1::uuid",
            user_id,
        )
        if existing:
            return existing

        customer = stripe.Customer.create(
            email=email,
            metadata={"dcn_user_id": user_id},
        )
        await conn.execute(
            "UPDATE dcn_users SET stripe_customer_id = $1 WHERE id = $2::uuid",
            customer.id, user_id,
        )
        logger.info("Created Stripe customer %s for user %s", customer.id, user_id)
        return customer.id


# ── Payment Intents (job submission) ─────────────────────────

async def create_payment_intent(
    user_id: str, email: str, amount_cents: int, platform_fee_cents: int,
) -> dict:
    """
    Create a Stripe PaymentIntent with manual capture (authorize only).
    Returns client_secret + payment_intent_id for the frontend.
    The job_id is set later when the job is actually created.
    """
    customer_id = await get_or_create_stripe_customer(user_id, email)

    pi = stripe.PaymentIntent.create(
        amount=amount_cents,
        currency=STRIPE_CURRENCY,
        customer=customer_id,
        capture_method="manual",
        metadata={"dcn_user_id": user_id},
    )

    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO payments (user_id, stripe_payment_intent_id, amount_cents,
                                  platform_fee_cents, currency, status)
            VALUES ($1::uuid, $2, $3, $4, $5, 'pending')
            """,
            user_id, pi.id, amount_cents, platform_fee_cents, STRIPE_CURRENCY,
        )

    logger.info("Created PaymentIntent %s for %d cents", pi.id, amount_cents)
    return {"client_secret": pi.client_secret, "payment_intent_id": pi.id}


async def link_payment_to_job(payment_intent_id: str, job_id: str) -> bool:
    """Associate a confirmed payment with a job after job creation."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE payments SET job_id = $1::uuid, status = 'authorized', updated_at = NOW() WHERE stripe_payment_intent_id = $2",
            job_id, payment_intent_id,
        )
        return result != "UPDATE 0"


async def capture_payment(job_id: str) -> bool:
    """Capture an authorized payment after job completion."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT stripe_payment_intent_id, status FROM payments WHERE job_id = $1::uuid AND status = 'authorized'",
            job_id,
        )
        if not row:
            return False

        try:
            stripe.PaymentIntent.capture(row["stripe_payment_intent_id"])
            await conn.execute(
                "UPDATE payments SET status = 'captured', updated_at = NOW() WHERE stripe_payment_intent_id = $1",
                row["stripe_payment_intent_id"],
            )
            logger.info("Captured payment %s for job %s", row["stripe_payment_intent_id"], job_id)
            return True
        except stripe.StripeError as e:
            logger.error("Failed to capture payment for job %s: %s", job_id, e)
            return False


async def refund_payment(job_id: str) -> bool:
    """Cancel/refund a payment for a failed or cancelled job."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT stripe_payment_intent_id, status FROM payments WHERE job_id = $1::uuid AND status IN ('authorized', 'captured')",
            job_id,
        )
        if not row:
            return False

        try:
            pi_id = row["stripe_payment_intent_id"]
            if row["status"] == "authorized":
                stripe.PaymentIntent.cancel(pi_id)
            else:
                stripe.Refund.create(payment_intent=pi_id)

            await conn.execute(
                "UPDATE payments SET status = 'refunded', updated_at = NOW() WHERE stripe_payment_intent_id = $1",
                pi_id,
            )
            logger.info("Refunded payment %s for job %s", pi_id, job_id)
            return True
        except stripe.StripeError as e:
            logger.error("Failed to refund payment for job %s: %s", job_id, e)
            return False


# ── Payment verification ─────────────────────────────────────

async def verify_payment_intent(payment_intent_id: str, user_id: str) -> dict | None:
    """Check that a payment intent exists, belongs to user, and is confirmed."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM payments WHERE stripe_payment_intent_id = $1 AND user_id = $2::uuid",
            payment_intent_id, user_id,
        )
        if not row:
            return None
        return dict(row)


# ── Stripe Connect (worker payouts) ─────────────────────────

async def create_worker_connect_link(worker_node_id: str) -> str:
    """Create or retrieve a Stripe Connect onboarding link for a worker."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        connect_id = await conn.fetchval(
            "SELECT stripe_connect_id FROM worker_nodes WHERE id = $1::uuid",
            worker_node_id,
        )
        if not connect_id:
            account = stripe.Account.create(
                type="express",
                metadata={"dcn_worker_node_id": worker_node_id},
            )
            connect_id = account.id
            await conn.execute(
                "UPDATE worker_nodes SET stripe_connect_id = $1 WHERE id = $2::uuid",
                connect_id, worker_node_id,
            )
            logger.info("Created Connect account %s for worker %s", connect_id, worker_node_id)

    link = stripe.AccountLink.create(
        account=connect_id,
        refresh_url=f"{BASE_URL}/billing/connect/refresh",
        return_url=f"{BASE_URL}/billing/connect/complete",
        type="account_onboarding",
    )
    return link.url


async def get_worker_connect_status(worker_node_id: str) -> dict:
    """Check if a worker has completed Stripe Connect onboarding."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        connect_id = await conn.fetchval(
            "SELECT stripe_connect_id FROM worker_nodes WHERE id = $1::uuid",
            worker_node_id,
        )
    if not connect_id:
        return {"connected": False, "account_id": None}

    try:
        account = stripe.Account.retrieve(connect_id)
        return {
            "connected": account.charges_enabled and account.payouts_enabled,
            "account_id": connect_id,
            "charges_enabled": account.charges_enabled,
            "payouts_enabled": account.payouts_enabled,
        }
    except stripe.StripeError:
        return {"connected": False, "account_id": connect_id}


# ── Worker transfers ─────────────────────────────────────────

async def transfer_to_worker(worker_node_id: str, job_id: str, amount_cents: int) -> str | None:
    """Transfer earnings to a worker's connected Stripe account."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        connect_id = await conn.fetchval(
            "SELECT stripe_connect_id FROM worker_nodes WHERE id = $1::uuid",
            worker_node_id,
        )
        if not connect_id:
            # Worker not onboarded — record as pending
            await conn.execute(
                """
                INSERT INTO worker_payouts (job_id, worker_node_id, amount_cents, status)
                VALUES ($1::uuid, $2::uuid, $3, 'pending')
                ON CONFLICT DO NOTHING
                """,
                job_id, worker_node_id, amount_cents,
            )
            logger.info("Worker %s not onboarded — payout pending (%d cents)", worker_node_id, amount_cents)
            return None

        try:
            transfer = stripe.Transfer.create(
                amount=amount_cents,
                currency=STRIPE_CURRENCY,
                destination=connect_id,
                metadata={"dcn_job_id": job_id, "dcn_worker_node_id": worker_node_id},
            )
            await conn.execute(
                """
                INSERT INTO worker_payouts (job_id, worker_node_id, stripe_transfer_id, amount_cents, status)
                VALUES ($1::uuid, $2::uuid, $3, $4, 'transferred')
                ON CONFLICT DO NOTHING
                """,
                job_id, worker_node_id, transfer.id, amount_cents,
            )
            logger.info("Transferred %d cents to worker %s (transfer %s)", amount_cents, worker_node_id, transfer.id)
            return transfer.id
        except stripe.StripeError as e:
            logger.error("Transfer to worker %s failed: %s", worker_node_id, e)
            await conn.execute(
                """
                INSERT INTO worker_payouts (job_id, worker_node_id, amount_cents, status)
                VALUES ($1::uuid, $2::uuid, $3, 'failed')
                ON CONFLICT DO NOTHING
                """,
                job_id, worker_node_id, amount_cents,
            )
            return None


async def process_job_payouts(job_id: str) -> dict:
    """
    After a job completes: capture payment, calculate worker shares, transfer.
    Called from the aggregator.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Check if this job has a payment to capture
        payment = await conn.fetchrow(
            "SELECT * FROM payments WHERE job_id = $1::uuid AND status = 'authorized'",
            job_id,
        )
        if not payment:
            return {"skipped": True, "reason": "no_payment"}

        # Capture the payment
        captured = await capture_payment(job_id)
        if not captured:
            return {"error": "capture_failed"}

        # Calculate actual worker earnings
        task_rows = await conn.fetch(
            """
            SELECT jt.task_payload, jt.worker_node_id,
                   tr.execution_time_seconds
            FROM job_tasks jt
            LEFT JOIN task_results tr ON tr.task_id = jt.id
            WHERE jt.job_id = $1 AND tr.execution_time_seconds IS NOT NULL
            """,
            job_id,
        )

    cost_data = calculate_actual_cost([dict(r) for r in task_rows])
    worker_earnings = cost_data.get("worker_earnings", {})

    transfers = {}
    for worker_id, earnings_dollars in worker_earnings.items():
        cents = _dollars_to_cents(earnings_dollars)
        if cents > 0:
            tid = await transfer_to_worker(str(worker_id), job_id, cents)
            transfers[str(worker_id)] = {"cents": cents, "transfer_id": tid}

    return {"captured": True, "transfers": transfers}


# ── Pro subscription ─────────────────────────────────────────

async def create_pro_subscription(user_id: str, email: str) -> dict:
    """Create a Stripe Checkout session for Pro tier ($5/mo)."""
    if not STRIPE_PRO_PRICE_ID:
        raise ValueError("STRIPE_PRO_PRICE_ID not configured")

    customer_id = await get_or_create_stripe_customer(user_id, email)

    session = stripe.checkout.Session.create(
        customer=customer_id,
        mode="subscription",
        line_items=[{"price": STRIPE_PRO_PRICE_ID, "quantity": 1}],
        success_url=f"{BASE_URL}/submit?upgrade=success",
        cancel_url=f"{BASE_URL}/submit?upgrade=cancelled",
        metadata={"dcn_user_id": user_id},
    )

    return {"checkout_url": session.url, "session_id": session.id}


async def cancel_pro_subscription(user_id: str) -> bool:
    """Cancel the user's Pro subscription."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        sub_id = await conn.fetchval(
            "SELECT stripe_subscription_id FROM dcn_users WHERE id = $1::uuid",
            user_id,
        )
        if not sub_id:
            return False

        try:
            stripe.Subscription.cancel(sub_id)
            await conn.execute(
                "UPDATE dcn_users SET tier = 'free', stripe_subscription_id = NULL WHERE id = $1::uuid",
                user_id,
            )
            logger.info("Cancelled Pro subscription %s for user %s", sub_id, user_id)
            return True
        except stripe.StripeError as e:
            logger.error("Failed to cancel subscription for user %s: %s", user_id, e)
            return False


# ── Webhook processing ───────────────────────────────────────

async def handle_webhook_event(event: stripe.Event) -> None:
    """Process a verified Stripe webhook event."""
    etype = event.type
    data = event.data.object

    if etype == "payment_intent.succeeded":
        pi_id = data.id
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE payments SET status = 'authorized', updated_at = NOW() WHERE stripe_payment_intent_id = $1 AND status = 'pending'",
                pi_id,
            )
        logger.info("PaymentIntent %s authorized via webhook", pi_id)

    elif etype == "payment_intent.payment_failed":
        pi_id = data.id
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE payments SET status = 'failed', updated_at = NOW() WHERE stripe_payment_intent_id = $1",
                pi_id,
            )
        logger.warning("PaymentIntent %s failed", pi_id)

    elif etype == "checkout.session.completed":
        # Pro subscription activated
        user_id = data.metadata.get("dcn_user_id")
        sub_id = data.subscription
        if user_id and sub_id:
            pool = await get_pool()
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE dcn_users SET tier = 'pro', stripe_subscription_id = $1 WHERE id = $2::uuid",
                    sub_id, user_id,
                )
            logger.info("User %s upgraded to Pro (subscription %s)", user_id, sub_id)

    elif etype == "customer.subscription.deleted":
        sub_id = data.id
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE dcn_users SET tier = 'free', stripe_subscription_id = NULL WHERE stripe_subscription_id = $1",
                sub_id,
            )
        logger.info("Subscription %s cancelled — user downgraded to free", sub_id)

    else:
        logger.debug("Unhandled webhook event type: %s", etype)
