"""
Subscription and quota management for DCN.

Defines plans, limits, and helper functions for checking/decrementing quotas.
"""
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from database import get_pool

logger = logging.getLogger("dcn.subscriptions")

# --- Plan Definitions ---

PLANS = {
    "free": {
        "name": "Free",
        "monthly_price": 0,
        "job_limit": 5,
        "worker_tiers": [1, 2],
        "priority": 1,
        "overage_allowed": False,
        "overage_price": 0,
    },
    "pro": {
        "name": "Pro",
        "monthly_price": 29,
        "job_limit": 50,
        "worker_tiers": [1, 2, 3, 4],
        "priority": 2,
        "overage_allowed": True,
        "overage_price": 0.50,
    },
    "team": {
        "name": "Team",
        "monthly_price": 99,
        "job_limit": 200,
        "worker_tiers": [1, 2, 3, 4],
        "priority": 3,
        "overage_allowed": True,
        "overage_price": 0.35,
    },
    "enterprise": {
        "name": "Enterprise",
        "monthly_price": None,  # Custom
        "job_limit": 1000000, # Representing unlimited
        "worker_tiers": [1, 2, 3, 4],
        "priority": 5,
        "overage_allowed": True,
        "overage_price": 0,
    }
}

# --- Database Helpers ---

async def get_subscription(user_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve the current subscription for a user."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM subscriptions WHERE user_id = $1::uuid",
            user_id
        )
        if row:
            return dict(row)
        
        # If no subscription record, check if user exists in dcn_users
        user_row = await conn.fetchrow("SELECT tier FROM dcn_users WHERE id = $1::uuid", user_id)
        if not user_row:
            return None
            
        # Create default subscription based on current tier
        current_tier = user_row["tier"] or "free"
        if current_tier not in PLANS:
            current_tier = "free"
            
        limit = PLANS[current_tier]["job_limit"]
        
        await conn.execute(
            """
            INSERT INTO subscriptions (user_id, plan, jobs_remaining)
            VALUES ($1::uuid, $2, $3)
            ON CONFLICT (user_id) DO NOTHING
            """,
            user_id, current_tier, limit
        )
        
        row = await conn.fetchrow(
            "SELECT * FROM subscriptions WHERE user_id = $1::uuid",
            user_id
        )
        return dict(row) if row else None

async def check_quota(user_id: str) -> bool:
    """Check if a user has enough quota to submit a job."""
    sub = await get_subscription(user_id)
    if not sub:
        return False
    
    plan_id = sub["plan"]
    plan = PLANS.get(plan_id, PLANS["free"])
    
    if sub["jobs_remaining"] > 0:
        return True
    
    if plan["overage_allowed"]:
        return True
        
    return False

async def decrement_quota(user_id: str) -> bool:
    """Decrement the jobs_remaining count for a user."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE subscriptions 
            SET jobs_remaining = GREATEST(0, jobs_remaining - 1),
                updated_at = NOW()
            WHERE user_id = $1::uuid
            RETURNING jobs_remaining, plan
            """,
            user_id
        )
        if not row:
            return False
        return True

async def reset_quotas_for_user(user_id: str, plan_id: str):
    """Reset the quota for a user based on their plan."""
    plan = PLANS.get(plan_id, PLANS["free"])
    limit = plan["job_limit"]
        
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE subscriptions 
            SET jobs_remaining = $1,
                billing_cycle = NOW(),
                updated_at = NOW()
            WHERE user_id = $2::uuid
            """,
            limit, user_id
        )

async def update_subscription_plan(user_id: str, plan_id: str, stripe_sub_id: Optional[str] = None):
    """Update a user's subscription plan."""
    if plan_id not in PLANS:
        raise ValueError(f"Invalid plan: {plan_id}")
        
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO subscriptions (user_id, plan, stripe_sub_id, jobs_remaining)
            VALUES ($1::uuid, $2, $3, $4)
            ON CONFLICT (user_id) DO UPDATE
            SET plan = EXCLUDED.plan,
                stripe_sub_id = EXCLUDED.stripe_sub_id,
                jobs_remaining = EXCLUDED.jobs_remaining,
                updated_at = NOW()
            """,
            user_id, plan_id, stripe_sub_id, PLANS[plan_id]["job_limit"]
        )
        
        # Also update the tier in dcn_users for backward compatibility
        await conn.execute(
            "UPDATE dcn_users SET tier = $1 WHERE id = $2::uuid",
            plan_id, user_id
        )
