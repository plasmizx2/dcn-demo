"""
Pricing engine for DCN jobs.

Estimates job cost before submission based on planned subtasks,
and calculates actual cost after completion from real execution times.

What affects the ESTIMATE vs the ACTUAL invoice
-----------------------------------------------
Estimate (pre-submission):
  - subtask count and tier (from planner)
  - assumed compute seconds per tier (ESTIMATED_SECONDS_PER_TIER)
  - data multiplier derived from dataset dimensions (n_rows, n_cols):
    at baseline (1K rows / 10 cols) the multiplier is 1.0; it grows
    sub-linearly via log2 up to DATASET_SCALE_CAP.

Actual (post-completion):
  - real execution_time_seconds recorded by workers
  - tier-based rate applied to those real seconds
  - dataset size does NOT retroactively adjust the actual cost; the
    multiplier is an estimate-time proxy for work that real timing captures.
"""

import math

from config import (
    BASE_RATES,
    TIER_MULTIPLIER,
    PLATFORM_FEE_PERCENT,
    ESTIMATED_SECONDS_PER_TIER,
    DATASET_ROWS_BASELINE,
    DATASET_COLS_BASELINE,
    DATASET_SCALE_CAP,
)


def _data_multiplier(n_rows: int | None, n_cols: int | None) -> float:
    """
    Sub-linear scale factor from dataset dimensions.

    Returns 1.0 when no stats are provided (neutral / unknown).
    1.0 exactly at (DATASET_ROWS_BASELINE rows, DATASET_COLS_BASELINE cols).

    Scaling:
      row_mult = clamp(1 + log2(n_rows / ROWS_BASELINE), 0.25, ∞)
      col_mult = clamp(1 + 0.5 * log2(n_cols / COLS_BASELINE), 0.5, ∞)
      result   = clamp(row_mult * col_mult, 0.25, DATASET_SCALE_CAP)

    Example multipliers:
      100 rows, 5 cols  → ~0.25  (tiny dataset, cheaper)
      1K rows, 10 cols  → 1.0    (baseline)
      10K rows, 20 cols → ~4.5
      75K rows, 16 cols → ~9.4   (built-in DCN demo datasets)
    """
    if n_rows is None and n_cols is None:
        return 1.0
    rows = max(1, n_rows or DATASET_ROWS_BASELINE)
    cols = max(1, n_cols or DATASET_COLS_BASELINE)
    row_mult = max(0.25, 1.0 + math.log2(rows / DATASET_ROWS_BASELINE))
    col_mult = max(0.5, 1.0 + 0.5 * math.log2(cols / DATASET_COLS_BASELINE))
    return round(min(DATASET_SCALE_CAP, row_mult * col_mult), 3)


def estimate_job_cost(
    subtasks: list[dict],
    *,
    n_rows: int | None = None,
    n_cols: int | None = None,
) -> dict:
    """
    Estimate total job cost from planner-generated subtasks.

    Parameters
    ----------
    subtasks : list[dict]
        Planner output. Each entry must have a ``task_payload`` with
        ``min_tier`` and optionally ``experiment_type``.
    n_rows : int | None
        Dataset row count from client preview (optional but recommended).
    n_cols : int | None
        Dataset column count from client preview (optional but recommended).

    Returns a breakdown including ``data_multiplier`` and ``dataset_stats``
    so callers can surface formula inputs in the UI.
    Platform fee is returned at 4-decimal precision so the UI can display
    sub-cent amounts (e.g. "< $0.01") rather than a misleading "$0.00".
    """
    data_mult = _data_multiplier(n_rows, n_cols)
    task_estimates = []
    total = 0.0

    for task in subtasks:
        payload = task.get("task_payload", {})
        min_tier = payload.get("min_tier", 2)

        base_rate = BASE_RATES.get("ml_experiment", 0.01)
        tier_mult = TIER_MULTIPLIER.get(min_tier, 1.0)
        est_seconds = ESTIMATED_SECONDS_PER_TIER.get(min_tier, 10)

        task_cost = round(base_rate * tier_mult * est_seconds * data_mult, 6)
        total += task_cost

        task_estimates.append({
            "task_name": task.get("task_name", "unknown"),
            "min_tier": min_tier,
            "estimated_seconds": est_seconds,
            "data_multiplier": data_mult,
            "estimated_cost": task_cost,
        })

    platform_fee_raw = total * PLATFORM_FEE_PERCENT / 100
    # Keep 4 decimal places so the UI can show "< $0.01" instead of "$0.00"
    platform_fee = round(platform_fee_raw, 4)
    compute_cost = round(total, 4)
    estimated_total = round(total + platform_fee_raw, 4)

    return {
        "subtask_count": len(subtasks),
        "compute_cost": compute_cost,
        "platform_fee": platform_fee,
        "platform_fee_percent": PLATFORM_FEE_PERCENT,
        "estimated_total": estimated_total,
        "data_multiplier": data_mult,
        "dataset_stats": {"n_rows": n_rows, "n_cols": n_cols},
        "task_estimates": task_estimates,
    }


def calculate_actual_cost(task_rows: list[dict]) -> dict:
    """
    Calculate actual job cost from completed task execution times.
    Each task_row should have: execution_time_seconds, min_tier (from task_payload).
    """
    total = 0.0
    worker_earnings = {}

    for row in task_rows:
        exec_time = float(row.get("execution_time_seconds") or 0)
        payload = row.get("task_payload", {})
        if isinstance(payload, str):
            import json
            try:
                payload = json.loads(payload)
            except (json.JSONDecodeError, TypeError):
                payload = {}

        min_tier = payload.get("min_tier", 2)
        base_rate = BASE_RATES.get("ml_experiment", 0.01)
        tier_mult = TIER_MULTIPLIER.get(min_tier, 1.0)

        task_cost = round(base_rate * tier_mult * exec_time, 4)
        total += task_cost

        worker_id = row.get("worker_node_id")
        if worker_id:
            worker_earnings[worker_id] = round(
                worker_earnings.get(worker_id, 0) + task_cost, 4
            )

    platform_fee = round(total * PLATFORM_FEE_PERCENT / 100, 4)
    total_with_fee = round(total + platform_fee, 4)

    return {
        "compute_cost": round(total, 4),
        "platform_fee": round(platform_fee, 4),
        "actual_total": total_with_fee,
        "worker_earnings": worker_earnings,
    }
