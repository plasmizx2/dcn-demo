"""
Centralized configuration constants.

All magic numbers and tuning parameters in one place.
Change once, applied everywhere.
"""

# ── Maintenance Loop ──────────────────────────────────────────
MAINTENANCE_INTERVAL_SECONDS: int = 60
STALE_TASK_TIMEOUT_MINUTES: int = 8
WORKER_PRUNE_TIMEOUT_MINUTES: int = 60

# ── Worker Behavior ──────────────────────────────────────────
HEARTBEAT_OFFLINE_SECONDS: int = 30
RETRY_BACKOFF_SECONDS: list[int] = [5, 15, 30]
RATE_LIMIT_BACKOFF_MULTIPLIER: int = 2
WORKER_POLL_INTERVAL_SECONDS: int = 5

# ── Task failure → requeue (another worker can claim after delay) ──
TASK_FAILURE_RETRY_DELAY_SECONDS: int = 60
MAX_TASK_FAILURE_RETRIES: int = 5

# ── Tier fallback (issue #4) ──
# If a task sat queued this long, effective min_tier drops by 1 so e.g. Tier 3 can claim Tier 4 work.
TIER_FALLBACK_AFTER_MINUTES: int = 2

# ── Auth ─────────────────────────────────────────────────────
SESSION_MAX_AGE_SECONDS: int = 86400  # 24 hours

# ── Task Types ───────────────────────────────────────────────
VALID_TASK_TYPES: set[str] = {
    "ml_experiment",
}

# ── Job Constraints ──────────────────────────────────────────
MIN_PRIORITY: int = 1
MAX_PRIORITY: int = 10
MIN_REWARD: float = 0.0

# ── Pricing ─────────────────────────────────────────────────
# Base rate per compute-second, keyed by task type (in dollars)
BASE_RATES: dict[str, float] = {
    "ml_experiment": 0.0015,
}
# Multiplier applied based on minimum worker tier required
TIER_MULTIPLIER: dict[int, float] = {1: 1.0, 2: 1.2, 3: 1.5, 4: 2.0}
# Estimated seconds per tier (used for pre-submission cost estimates)
ESTIMATED_SECONDS_PER_TIER: dict[int, int] = {1: 3, 2: 5, 3: 10, 4: 18}
# Platform fee as a percentage of compute cost
PLATFORM_FEE_PERCENT: float = 15.0

# ── Aggregation ─────────────────────────────────────────────
CONCAT_TASK_TYPES: set[str] = set()
