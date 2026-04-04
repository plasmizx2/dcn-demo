"""
Stripe billing integration for DCN.

Handles:
- PaymentIntents for job submitters (charge before job enters queue)
- Stripe Connect accounts for workers (receive earnings via Transfer)
- Pro tier subscriptions ($5/mo)
- Refunds when jobs fail or are cancelled
- Webhook event construction for incoming Stripe events
- Tier enforcement (free / paygo / pro)

All low-level Stripe SDK calls are synchronous wrappers. The async helpers
(tier management, payout orchestration) use the DB pool directly.
"""
import os
import logging
import math

import stripe

from config import STRIPE_MINIMUM_CHARGE_CENTS

logger = logging.getLogger("dcn.billing")

# ── Stripe config ───────────────────────────────────────────
stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_PUBLISHABLE_KEY: str = os.getenv("STRIPE_PUBLISHABLE_KEY", "")
STRIPE_WEBHOOK_SECRET: str = os.getenv("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PRO_PRICE_ID: str = os.getenv("STRIPE_PRO_PRICE_ID", "")
BASE_URL: str = os.getenv("BASE_URL", "http://localhost:8000")


def is_enabled() -> bool:
    """True when a Stripe secret key is configured."""
    return bool(stripe.api_key)


def dollars_to_cents(dollars: float) -> int:
    """Convert a dollar amount to integer cents, floored at Stripe's $0.50 minimum."""
    return max(STRIPE_MINIMUM_CHARGE_CENTS, round(dollars * 100))


def _dollars_to_cents_raw(amount: float) -> int:
    """Convert dollars to cents without Stripe minimum (for internal calculations)."""
    return max(0, math.ceil(amount * 100))


# ── PaymentIntents ────────────────────────────────────────────────────────────

def create_payment_intent(amount_cents: int, metadata: dict | None = None) -> dict:
    """Create a PaymentIntent and return its client_secret + id."""
    pi = stripe.PaymentIntent.create(
        amount=amount_cents,
        currency="usd",
        metadata=metadata or {},
        automatic_payment_methods={"enabled": True},
    )
    return {"client_secret": pi.client_secret, "payment_intent_id": pi.id}


def retrieve_payment_intent(pi_id: str) -> dict:
    """Retrieve a PaymentIntent's current status and amount."""
    pi = stripe.PaymentIntent.retrieve(pi_id)
    return {"id": pi.id, "status": pi.status, "amount": pi.amount}


def create_refund(pi_id: str) -> dict:
    """Issue a full refund for a PaymentIntent."""
    refund = stripe.Refund.create(payment_intent=pi_id)
    return {"id": refund.id, "status": refund.status}


# ── Stripe Connect (worker payouts) ──────────────────────────────────────────

def create_connect_account(email: str) -> str:
    """Create a Stripe Express account for a worker. Returns the Stripe account ID."""
    account = stripe.Account.create(
        type="express",
        email=email,
        capabilities={"transfers": {"requested": True}},
    )
    return account.id


def create_onboarding_link(account_id: str, return_url: str, refresh_url: str) -> str:
    """Generate a one-time Stripe Connect onboarding URL for an Express account."""
    link = stripe.AccountLink.create(
        account=account_id,
        refresh_url=refresh_url,
        return_url=return_url,
        type="account_onboarding",
    )
    return link.url


def retrieve_account(account_id: str) -> dict:
    """Return capability flags for a Connect account."""
    account = stripe.Account.retrieve(account_id)
    return {
        "id": account.id,
        "charges_enabled": account.charges_enabled,
        "payouts_enabled": account.payouts_enabled,
        "details_submitted": account.details_submitted,
    }


def create_transfer(amount_cents: int, destination: str, transfer_group: str) -> dict:
    """Transfer earnings (from platform balance) to a connected worker account."""
    transfer = stripe.Transfer.create(
        amount=amount_cents,
        currency="usd",
        destination=destination,
        transfer_group=transfer_group,
    )
    return {"id": transfer.id, "amount": transfer.amount}


# ── Webhooks ──────────────────────────────────────────────────────────────────

def construct_webhook_event(payload: bytes, sig_header: str):
    """Verify and parse an incoming Stripe webhook payload. Raises on bad signature."""
    return stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)


# ── Pro subscription ─────────────────────────────────────────────────────────

async def create_pro_subscription(user_id: str, email: str) -> dict:
    """Create a Stripe Checkout session for Pro tier ($5/mo)."""
    if not STRIPE_PRO_PRICE_ID:
        raise ValueError("STRIPE_PRO_PRICE_ID not configured")

    from database import get_pool

    pool = await get_pool()
    async with pool.acquire() as conn:
        customer_id = await conn.fetchval(
            "SELECT stripe_customer_id FROM dcn_users WHERE id = $1::uuid", user_id,
        )
        if not customer_id:
            customer = stripe.Customer.create(email=email, metadata={"dcn_user_id": user_id})
            customer_id = customer.id
            await conn.execute(
                "UPDATE dcn_users SET stripe_customer_id = $1 WHERE id = $2::uuid",
                customer_id, user_id,
            )

    session = stripe.checkout.Session.create(
        customer=customer_id,
        mode="subscription",
        line_items=[{"price": STRIPE_PRO_PRICE_ID, "quantity": 1}],
        success_url=f"{BASE_URL}/account?upgrade=success",
        cancel_url=f"{BASE_URL}/account?upgrade=cancelled",
        metadata={"dcn_user_id": user_id},
    )
    return {"checkout_url": session.url, "session_id": session.id}


async def cancel_pro_subscription(user_id: str) -> bool:
    """Cancel the user's Pro subscription."""
    from database import get_pool

    pool = await get_pool()
    async with pool.acquire() as conn:
        sub_id = await conn.fetchval(
            "SELECT stripe_subscription_id FROM dcn_users WHERE id = $1::uuid", user_id,
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


# ── Webhook event processing ─────────────────────────────────────────────────

async def handle_webhook_event(event) -> None:
    """Process a verified Stripe webhook event."""
    from database import get_pool

    etype = event.type
    data = event.data.object

    if etype == "checkout.session.completed":
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

    elif etype == "account.updated":
        acct_id = data.id
        if data.charges_enabled and data.payouts_enabled:
            pool = await get_pool()
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE stripe_accounts SET status = 'active', updated_at = NOW() WHERE stripe_account_id = $1",
                    acct_id,
                )
            logger.info("Connect account %s is now active", acct_id)

    else:
        logger.debug("Unhandled webhook event type: %s", etype)


# ── Worker payout orchestration ───────────────────────────────────────────────

async def trigger_worker_payouts(job_id: str) -> None:
    """
    After a job completes, calculate per-worker earnings and send Stripe Transfers.

    Only transfers to workers whose Connect accounts have payouts_enabled.
    Failures are logged but never re-raised — the job has already completed.
    """
    if not is_enabled():
        return

    from database import get_pool
    from pricing import calculate_actual_cost

    pool = await get_pool()
    async with pool.acquire() as conn:
        tasks = await conn.fetch(
            """
            SELECT jt.worker_node_id, jt.task_payload, tr.execution_time_seconds
            FROM job_tasks jt
            LEFT JOIN task_results tr ON tr.task_id = jt.id
            WHERE jt.job_id = $1 AND jt.status = 'submitted'
            """,
            job_id,
        )
        if not tasks:
            return

        task_rows = [
            {
                "worker_node_id": str(t["worker_node_id"]) if t["worker_node_id"] else None,
                "task_payload": t["task_payload"],
                "execution_time_seconds": t["execution_time_seconds"],
            }
            for t in tasks
        ]

        cost = calculate_actual_cost(task_rows)
        worker_earnings: dict[str, float] = cost.get("worker_earnings", {})
        if not worker_earnings:
            return

        transfer_group = f"job_{job_id}"

        for worker_node_id, earnings_dollars in worker_earnings.items():
            worker_row = await conn.fetchrow(
                "SELECT user_id FROM worker_nodes WHERE id = $1::uuid",
                worker_node_id,
            )
            if not worker_row or not worker_row["user_id"]:
                continue

            stripe_row = await conn.fetchrow(
                "SELECT stripe_account_id, status FROM stripe_accounts WHERE user_id = $1::uuid",
                worker_row["user_id"],
            )
            if not stripe_row or stripe_row["status"] != "active":
                continue

            amount_cents = max(1, round(earnings_dollars * 100))
            try:
                transfer = create_transfer(amount_cents, stripe_row["stripe_account_id"], transfer_group)
                await conn.execute(
                    """
                    INSERT INTO payments (job_id, user_id, stripe_id, amount_cents, status, payment_type)
                    VALUES ($1, $2, $3, $4, 'succeeded', 'payout')
                    """,
                    job_id,
                    worker_row["user_id"],
                    transfer["id"],
                    amount_cents,
                )
                logger.info(
                    "Transferred %d cents to worker %s (job %s)",
                    amount_cents, worker_node_id[:8], job_id[:8],
                )
            except Exception as exc:
                logger.error(
                    "Failed to transfer to worker %s for job %s: %s",
                    worker_node_id[:8], job_id[:8], exc,
                )


async def refund_job_payment(job_id: str) -> None:
    """
    Issue a refund for the charge recorded against a job (on failure/cancellation).

    Failures are logged and swallowed — the job status change should not be blocked.
    """
    if not is_enabled():
        return

    from database import get_pool

    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, stripe_id FROM payments
            WHERE job_id = $1 AND payment_type = 'charge' AND status = 'succeeded'
            LIMIT 1
            """,
            job_id,
        )
        if not row:
            return

        try:
            result = create_refund(row["stripe_id"])
            await conn.execute(
                "UPDATE payments SET status = 'refunded' WHERE id = $1",
                row["id"],
            )
            logger.info("Refunded payment %s for job %s (refund %s)", row["stripe_id"][:16], job_id[:8], result["id"])
        except Exception as exc:
            logger.error("Failed to refund payment for job %s: %s", job_id[:8], exc)
