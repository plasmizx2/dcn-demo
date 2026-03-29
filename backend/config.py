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

# ── Auth ─────────────────────────────────────────────────────
SESSION_MAX_AGE_SECONDS: int = 86400  # 24 hours

# ── Task Types ───────────────────────────────────────────────
VALID_TASK_TYPES: set[str] = {
    "document_analysis",
    "codebase_review",
    "website_builder",
    "research_pipeline",
    "data_processing",
    "ml_experiment",
    "image_processing",
    "web_scraping",
    "audio_transcription",
    "sentiment_classification",
}

# ── Job Constraints ──────────────────────────────────────────
MIN_PRIORITY: int = 1
MAX_PRIORITY: int = 10
MIN_REWARD: float = 0.0

# ── External Integrations ───────────────────────────────────
GITHUB_API_TIMEOUT_SECONDS: int = 15
MAX_FILES_PER_CODEBASE_TASK: int = 5

# ── Aggregation ─────────────────────────────────────────────
CONCAT_TASK_TYPES: set[str] = {
    "codebase_review", "website_builder", "data_processing",
    "image_processing", "web_scraping", "audio_transcription",
    "sentiment_classification",
}
