"""
Pricing engine for DCN jobs.

Estimates job cost before submission based on planned subtasks,
and calculates actual cost after completion from real execution times.
"""

from config import (
    BASE_RATES,
    TIER_MULTIPLIER,
    PLATFORM_FEE_PERCENT,
    ESTIMATED_SECONDS_PER_TIER,
)


def estimate_job_cost(subtasks: list[dict]) -> dict:
    """
    Estimate total job cost from planner-generated subtasks.
    Returns breakdown with per-task estimates and totals.
    """
    task_estimates = []
    total = 0.0

    for task in subtasks:
        payload = task.get("task_payload", {})
        task_type = payload.get("experiment_type", "ml_experiment")
        min_tier = payload.get("min_tier", 2)

        base_rate = BASE_RATES.get("ml_experiment", 0.01)
        tier_mult = TIER_MULTIPLIER.get(min_tier, 1.0)
        est_seconds = ESTIMATED_SECONDS_PER_TIER.get(min_tier, 10)

        task_cost = round(base_rate * tier_mult * est_seconds, 4)
        total += task_cost

        task_estimates.append({
            "task_name": task.get("task_name", "unknown"),
            "min_tier": min_tier,
            "estimated_seconds": est_seconds,
            "estimated_cost": task_cost,
        })

    platform_fee = round(total * PLATFORM_FEE_PERCENT / 100, 4)
    total_with_fee = round(total + platform_fee, 2)

    return {
        "subtask_count": len(subtasks),
        "compute_cost": round(total, 2),
        "platform_fee": round(platform_fee, 2),
        "platform_fee_percent": PLATFORM_FEE_PERCENT,
        "estimated_total": total_with_fee,
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
    total_with_fee = round(total + platform_fee, 2)

    return {
        "compute_cost": round(total, 2),
        "platform_fee": round(platform_fee, 2),
        "actual_total": total_with_fee,
        "worker_earnings": worker_earnings,
    }
