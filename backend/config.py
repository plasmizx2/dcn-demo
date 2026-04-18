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
# Kept low so DCN undercuts self-hosted cloud compute for convenience
BASE_RATES: dict[str, float] = {
    "ml_experiment": 0.0001,
}
# Multiplier applied based on minimum worker tier required
TIER_MULTIPLIER: dict[int, float] = {1: 1.0, 2: 1.2, 3: 1.5, 4: 2.0}
# Estimated seconds per tier (used for pre-submission cost estimates)
ESTIMATED_SECONDS_PER_TIER: dict[int, int] = {1: 3, 2: 5, 3: 8, 4: 14}
# Platform fee as a percentage of compute cost
PLATFORM_FEE_PERCENT: float = 15.0

# ── Dataset scale factors (for pre-submission cost estimates) ─
# Estimates apply a sub-linear multiplier based on dataset dimensions.
# At the baseline (ROWS_BASELINE rows, COLS_BASELINE cols) the multiplier is 1.0.
# Uses log2 scaling so cost grows meaningfully but not explosively with size.
DATASET_ROWS_BASELINE: int = 1_000   # 1K rows → data_multiplier 1.0
DATASET_COLS_BASELINE: int = 10      # 10 cols → data_multiplier 1.0
DATASET_SCALE_CAP: float = 10.0     # multiplier is capped at 10× baseline

# ── Task Timeouts ──────────────────────────────────────────
# Max seconds a single ML training call (cross_validate + fit) may run
TASK_TRAINING_TIMEOUT_SECONDS: int = 300  # 5 minutes

# Max minutes a job may run before the maintenance loop force-fails it
MAX_JOB_DURATION_MINUTES: int = 60  # 1 hour

# ── Stripe ───────────────────────────────────────────────────
# Stripe's minimum charge is $0.50; keep cents here so it's obvious
STRIPE_MINIMUM_CHARGE_CENTS: int = 50

# ── Aggregation ─────────────────────────────────────────────
CONCAT_TASK_TYPES: set[str] = set()

# ── User Tiers ──────────────────────────────────────────────
FREE_TIER_DAILY_JOB_LIMIT: int = 3
