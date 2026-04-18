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

async def create_pro_subscription(user_id: str, email: str, base_url: str | None = None) -> dict:
    """Create a Stripe Checkout session for Pro tier ($5/mo)."""
    if not STRIPE_PRO_PRICE_ID:
        raise ValueError("STRIPE_PRO_PRICE_ID not configured")

    from database import get_pool

    base = base_url or BASE_URL
    uid = str(user_id)

    pool = await get_pool()
    async with pool.acquire() as conn:
        customer_id = await conn.fetchval(
            "SELECT stripe_customer_id FROM dcn_users WHERE id = $1::uuid", uid,
        )
        if not customer_id:
            customer = stripe.Customer.create(email=email, metadata={"dcn_user_id": uid})
            customer_id = customer.id
            await conn.execute(
                "UPDATE dcn_users SET stripe_customer_id = $1 WHERE id = $2::uuid",
                customer_id, uid,
            )

    session = stripe.checkout.Session.create(
        customer=customer_id,
        mode="subscription",
        line_items=[{"price": STRIPE_PRO_PRICE_ID, "quantity": 1}],
        success_url=f"{base}/account?upgrade=success&session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{base}/account?upgrade=cancelled",
        metadata={"dcn_user_id": uid},
    )
    return {"checkout_url": session.url, "session_id": session.id}


async def create_topup_checkout_session(user_id: str, email: str, amount_cents: int, base_url: str | None = None) -> dict:
    """Create a Stripe Checkout session to top up user balance."""
    from database import get_pool
    base = base_url or BASE_URL
    uid = str(user_id)
    pool = await get_pool()
    async with pool.acquire() as conn:
        customer_id = await conn.fetchval(
            "SELECT stripe_customer_id FROM dcn_users WHERE id = $1::uuid", uid,
        )
        if not customer_id:
            customer = stripe.Customer.create(email=email, metadata={"dcn_user_id": uid})
            customer_id = customer.id
            await conn.execute(
                "UPDATE dcn_users SET stripe_customer_id = $1 WHERE id = $2::uuid",
                customer_id, uid,
            )
    session = stripe.checkout.Session.create(
        customer=customer_id,
        mode="payment",
        line_items=[{
            "price_data": {
                "currency": "usd",
                "unit_amount": amount_cents,
                "product_data": {"name": f"DCN Balance Top-Up (${amount_cents/100:.2f})"},
            },
            "quantity": 1,
        }],
        success_url=f"{base}/account?topup=success&session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{base}/account?topup=cancelled",
        metadata={"dcn_user_id": uid, "topup_amount_cents": str(amount_cents)},
    )
    return {"checkout_url": session.url, "session_id": session.id}


async def verify_and_credit_topup(session_id: str, user_id: str) -> dict:
    """Verify a Checkout session and credit balance if not already done."""
    from database import get_pool

    session = stripe.checkout.Session.retrieve(session_id)
    if session.payment_status != "paid":
        return {"credited": False, "reason": "not_paid"}

    # Access metadata using attribute access (StripeObject)
    topup_amount = getattr(session.metadata, "topup_amount_cents", None) if session.metadata else None
    session_user = getattr(session.metadata, "dcn_user_id", None) if session.metadata else None
    if not topup_amount or str(session_user) != str(user_id):
        return {"credited": False, "reason": "invalid_metadata"}

    amount_cents = int(topup_amount)
    pool = await get_pool()
    async with pool.acquire() as conn:
        already = await conn.fetchval(
            "SELECT 1 FROM balance_transactions WHERE reference_id = $1 AND tx_type = 'topup'",
            session_id,
        )
        if already:
            balance = await conn.fetchval("SELECT balance_cents FROM dcn_users WHERE id = $1::uuid", str(user_id))
            return {"credited": False, "reason": "already_credited", "balance_cents": balance or 0}

        async with conn.transaction():
            new_balance = await conn.fetchval(
                "UPDATE dcn_users SET balance_cents = balance_cents + $1 WHERE id = $2::uuid RETURNING balance_cents",
                amount_cents, str(user_id),
            )
            await conn.execute(
                """INSERT INTO balance_transactions (user_id, amount_cents, balance_after, tx_type, reference_id, description)
                   VALUES ($1::uuid, $2, $3, 'topup', $4, $5)""",
                str(user_id), amount_cents, new_balance, session_id, f"Top-up ${amount_cents/100:.2f}",
            )
    return {"credited": True, "balance_cents": new_balance, "amount_cents": amount_cents}


async def verify_and_activate_pro(session_id: str, user_id: str) -> dict:
    """Verify a Pro subscription Checkout session and activate Pro tier."""
    from database import get_pool

    session = stripe.checkout.Session.retrieve(session_id)
    if session.payment_status != "paid":
        return {"activated": False, "reason": "not_paid"}

    session_user = getattr(session.metadata, "dcn_user_id", None) if session.metadata else None
    sub_id = session.subscription

    if not sub_id or str(session_user) != str(user_id):
        return {"activated": False, "reason": "invalid_metadata"}

    pool = await get_pool()
    async with pool.acquire() as conn:
        # Check if already activated for this subscription
        already = await conn.fetchval(
            "SELECT 1 FROM dcn_users WHERE id = $1::uuid AND stripe_subscription_id = $2",
            str(user_id), sub_id,
        )
        if already:
            return {"activated": False, "reason": "already_activated"}

        async with conn.transaction():
            await conn.execute(
                "UPDATE dcn_users SET tier = 'pro', stripe_subscription_id = $1 WHERE id = $2::uuid",
                sub_id, str(user_id),
            )
    return {"activated": True, "tier": "pro", "subscription_id": sub_id}


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

    print(f"[HANDLER] Processing event type: {etype}", flush=True)

    if etype == "checkout.session.completed":
        user_id = getattr(data.metadata, "dcn_user_id", None) if data.metadata else None
        topup_amount = getattr(data.metadata, "topup_amount_cents", None) if data.metadata else None
        sub_id = data.subscription

        print(f"[HANDLER] checkout.session.completed: user_id={user_id}, topup_amount={topup_amount}, sub_id={sub_id}", flush=True)

        if user_id and topup_amount:
            # Top-up: credit user balance
            amount_cents = int(topup_amount)
            pool = await get_pool()
            async with pool.acquire() as conn:
                # Idempotency: check if already credited
                already = await conn.fetchval(
                    "SELECT 1 FROM balance_transactions WHERE reference_id = $1 AND tx_type = 'topup'",
                    data.id,
                )
                if not already:
                    async with conn.transaction():
                        new_balance = await conn.fetchval(
                            "UPDATE dcn_users SET balance_cents = balance_cents + $1 WHERE id = $2::uuid RETURNING balance_cents",
                            amount_cents, user_id,
                        )
                        await conn.execute(
                            """INSERT INTO balance_transactions (user_id, amount_cents, balance_after, tx_type, reference_id, description)
                               VALUES ($1::uuid, $2, $3, 'topup', $4, $5)""",
                            user_id, amount_cents, new_balance, data.id, f"Top-up ${amount_cents/100:.2f}",
                        )
                    print(f"[HANDLER] User {user_id} topped up {amount_cents} cents (new balance: {new_balance})", flush=True)

        elif user_id and sub_id:
            # Pro subscription
            pool = await get_pool()
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE dcn_users SET tier = 'pro', stripe_subscription_id = $1 WHERE id = $2::uuid",
                    sub_id, user_id,
                )
            print(f"[HANDLER] User {user_id} upgraded to Pro (subscription {sub_id})", flush=True)

    elif etype == "customer.subscription.deleted":
        sub_id = data.id
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE dcn_users SET tier = 'free', stripe_subscription_id = NULL WHERE stripe_subscription_id = $1",
                sub_id,
            )
        print(f"[HANDLER] Subscription {sub_id} cancelled — user downgraded to free", flush=True)

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


async def refund_job_balance(job_id: str) -> None:
    """Refund balance for a failed paygo job."""
    from database import get_pool
    pool = await get_pool()
    async with pool.acquire() as conn:
        tx = await conn.fetchrow(
            "SELECT user_id, amount_cents FROM balance_transactions WHERE reference_id = $1 AND tx_type = 'job_deduction' LIMIT 1",
            str(job_id),
        )
        if not tx:
            return
        refund_cents = abs(tx["amount_cents"])
        async with conn.transaction():
            new_balance = await conn.fetchval(
                "UPDATE dcn_users SET balance_cents = balance_cents + $1 WHERE id = $2::uuid RETURNING balance_cents",
                refund_cents, tx["user_id"],
            )
            await conn.execute(
                """INSERT INTO balance_transactions (user_id, amount_cents, balance_after, tx_type, reference_id, description)
                   VALUES ($1::uuid, $2, $3, 'refund', $4, 'Refund for failed job')""",
                tx["user_id"], refund_cents, new_balance, str(job_id),
            )
        logger.info("Refunded %d cents to user %s for job %s", refund_cents, str(tx["user_id"])[:8], str(job_id)[:8])
