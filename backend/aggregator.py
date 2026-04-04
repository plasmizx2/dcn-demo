"""
Aggregation: combine task results into a final job output.

Currently focused on ml_experiment — ranks experiment results
and produces a structured comparison report.
"""

import asyncio
import logging

from billing import process_job_payouts

logger = logging.getLogger("dcn.aggregator")


async def aggregate_job(conn, job_id: str) -> bool:
    """
    Check if all tasks for a job are submitted.
    If yes, combine results and update the job.
    Returns True if aggregation ran, False if tasks still pending.
    """
    # Count total vs terminal tasks (submitted or failed)
    counts = await conn.fetchrow(
        """
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE status = 'submitted') AS submitted,
            COUNT(*) FILTER (WHERE status IN ('submitted', 'failed')) AS done
        FROM job_tasks
        WHERE job_id = $1
        """,
        job_id,
    )

    if counts["done"] < counts["total"]:
        return False  # Some tasks still queued/running

    if counts["submitted"] == 0:
        return False  # All failed — fail_task handles the job status

    # All tasks done — fetch job info
    job = await conn.fetchrow("SELECT * FROM jobs WHERE id = $1", job_id)

    # Fetch results ordered by task_order
    results = await conn.fetch(
        """
        SELECT jt.task_order, jt.task_name, tr.result_text
        FROM job_tasks jt
        JOIN task_results tr ON tr.task_id = jt.id
        WHERE jt.job_id = $1
        ORDER BY jt.task_order
        """,
        job_id,
    )

    try:
        final_output = _aggregate_ml_experiment(results, job)
    except Exception as e:
        logger.warning("ML experiment aggregation failed: %s — falling back", e)
        final_output = _concatenate_results(results)

    # Set job status based on whether all tasks succeeded
    job_status = 'completed' if counts['submitted'] == counts['total'] else 'failed'

    # Update job with final output and status
    await conn.execute(
        """
        UPDATE jobs
        SET final_output = $1, status = $2, updated_at = NOW()
        WHERE id = $3
        """,
        final_output,
        job_status,
        job_id,
    )

    # Log completion event
    await conn.execute(
        """
        INSERT INTO job_events (job_id, event_type, message)
        VALUES ($1, 'job_completed', 'Job aggregation completed')
        """,
        job_id,
    )

    # Trigger payment capture + worker payouts
    if job_status == 'completed':
        try:
            payout_result = await process_job_payouts(job_id)
            if payout_result.get("captured"):
                logger.info("Payment captured and worker payouts initiated for job %s", job_id)
        except Exception as e:
            logger.error("Payout processing failed for job %s: %s", job_id, e)
            # Don't fail aggregation — payouts can be retried

    return True


def _concatenate_results(results: list) -> str:
    """Simple fallback concatenation."""
    sections = []
    for r in results:
        sections.append(
            f"=== {r['task_name']} ===\n\n{r['result_text']}"
        )
    return "\n\n---\n\n".join(sections)


def parse_ml_experiments_from_task_rows(results: list) -> list[dict]:
    """
    Extract embedded ```json``` metrics dicts from each task result (same logic as aggregation).
    Used by export and by _aggregate_ml_experiment.
    """
    import re
    import json as json_mod

    experiments = []
    for r in results:
        text = r["result_text"] or ""
        json_match = re.search(r"```json\s*\n(\{.*?\})\s*\n```", text, re.DOTALL)
        if json_match:
            try:
                data = json_mod.loads(json_match.group(1))
                experiments.append(data)
            except json_mod.JSONDecodeError:
                pass
    return experiments


def sort_ml_experiments_by_metric(experiments: list) -> list[dict]:
    """Return a new list sorted best-first (same ordering as the markdown report)."""
    if not experiments:
        return []
    exp = list(experiments)
    task_category = exp[0].get("task_category", "regression")
    if task_category == "regression":
        exp.sort(key=lambda x: x.get("r2", 0), reverse=True)
    else:
        exp.sort(key=lambda x: x.get("f1", 0), reverse=True)
    return exp


def _aggregate_ml_experiment(results: list, job: dict) -> str:
    """
    Custom aggregation for ml_experiment: parse JSON metrics from each
    experiment result, rank them, and produce a structured comparison report.
    Now includes CV scores, compute time breakdown, and more metrics.
    """
    import json as json_mod

    experiments = parse_ml_experiments_from_task_rows(results)

    if not experiments:
        return _concatenate_results(results)

    experiments = sort_ml_experiments_by_metric(experiments)
    task_category = experiments[0].get("task_category", "regression")

    if task_category == "regression":
        primary_metric = "R²"
    else:
        primary_metric = "F1"

    best = experiments[0]
    dataset_name = best.get("dataset_name", "unknown")
    target = best.get("target", "unknown")
    n_experiments = len(experiments)
    total_compute_time = sum(e.get("total_time_seconds", e.get("train_time_seconds", 0)) for e in experiments)
    total_cv_time = sum(e.get("cv_time_seconds", 0) for e in experiments)
    n_total = best.get("n_total", "?")
    cv_folds = best.get("cv_folds", 5)

    lines = []
    lines.append("# ML Experiment Results\n")

    # Conclusion
    lines.append("## Conclusion\n")
    lines.append(
        f"Across **{n_experiments} experiments** on the **{dataset_name}** dataset "
        f"({n_total:,} samples, target: `{target}`), the best-performing model was "
        f"**{best.get('model_display', best.get('model_type', 'Unknown'))}** "
        f"with {primary_metric} = **{best.get('primary_metric_value', 'N/A')}**.\n"
    )
    lines.append(
        f"All models were evaluated with **{cv_folds}-fold cross-validation** "
        f"and a held-out 20% test set. Total distributed compute time: **{round(total_compute_time, 2)}s** "
        f"(sequential equivalent: ~{round(total_compute_time, 1)}s, but run in parallel across workers).\n"
    )

    # Best Model
    lines.append("## Best Model\n")
    lines.append(f"- **Model:** {best.get('model_display', best.get('model_type'))}")
    if task_category == "regression":
        lines.append(f"- **R² Score:** {best.get('r2', 'N/A')}")
        lines.append(f"- **MSE:** {best.get('mse', 'N/A')}")
        lines.append(f"- **MAE:** {best.get('mae', 'N/A')}")
        lines.append(f"- **CV R² (mean +/- std):** {best.get('cv_r2_mean', 'N/A')} +/- {best.get('cv_r2_std', 'N/A')}")
    else:
        lines.append(f"- **F1 Score:** {best.get('f1', 'N/A')}")
        lines.append(f"- **Accuracy:** {best.get('accuracy', 'N/A')}")
        lines.append(f"- **Precision:** {best.get('precision', 'N/A')}")
        lines.append(f"- **Recall:** {best.get('recall', 'N/A')}")
        lines.append(f"- **CV F1 (mean +/- std):** {best.get('cv_f1_mean', 'N/A')} +/- {best.get('cv_f1_std', 'N/A')}")
    lines.append(f"- **Features:** {len(best.get('features', []))} features")
    params_str = ', '.join(f"{k}={v}" for k, v in best.get('params', {}).items())
    lines.append(f"- **Config:** {params_str or 'defaults'}")
    lines.append(f"- **Total Time:** {best.get('total_time_seconds', 'N/A')}s (CV: {best.get('cv_time_seconds', '?')}s + Train: {best.get('train_time_seconds', '?')}s)\n")

    # Model Comparison Table
    lines.append("## Model Comparison\n")
    if task_category == "regression":
        lines.append("| Rank | Model | R² | CV R² | MSE | MAE | Total Time | Features |")
        lines.append("|------|-------|----|-------|-----|-----|------------|----------|")
        for i, exp in enumerate(experiments, 1):
            model_name = exp.get('model_display', exp.get('model_type', '?'))
            r2_val = exp.get('r2', 'N/A')
            cv_r2 = f"{exp.get('cv_r2_mean', '?')}+/-{exp.get('cv_r2_std', '?')}"
            mse_val = exp.get('mse', 'N/A')
            mae_val = exp.get('mae', 'N/A')
            tt = exp.get('total_time_seconds', exp.get('train_time_seconds', 'N/A'))
            n_feat = len(exp.get('features', []))
            marker = " 🏆" if i == 1 else ""
            lines.append(f"| {i} | {model_name}{marker} | {r2_val} | {cv_r2} | {mse_val} | {mae_val} | {tt}s | {n_feat} |")
    else:
        lines.append("| Rank | Model | F1 | CV F1 | Accuracy | Precision | Recall | Total Time | Features |")
        lines.append("|------|-------|----| ------|----------|-----------|--------|------------|----------|")
        for i, exp in enumerate(experiments, 1):
            model_name = exp.get('model_display', exp.get('model_type', '?'))
            f1_val = exp.get('f1', 'N/A')
            cv_f1 = f"{exp.get('cv_f1_mean', '?')}+/-{exp.get('cv_f1_std', '?')}"
            acc_val = exp.get('accuracy', 'N/A')
            prec_val = exp.get('precision', 'N/A')
            rec_val = exp.get('recall', 'N/A')
            tt = exp.get('total_time_seconds', exp.get('train_time_seconds', 'N/A'))
            n_feat = len(exp.get('features', []))
            marker = " 🏆" if i == 1 else ""
            lines.append(f"| {i} | {model_name}{marker} | {f1_val} | {cv_f1} | {acc_val} | {prec_val} | {rec_val} | {tt}s | {n_feat} |")
    lines.append("")

    # Execution Summary
    lines.append("## Execution Summary\n")
    lines.append(f"- **{n_experiments} experiments** distributed across available worker nodes")
    lines.append(f"- **Total compute time:** {round(total_compute_time, 2)}s (CV: {round(total_cv_time, 2)}s)")
    lines.append(f"- **Dataset:** {dataset_name} ({best.get('n_total', '?'):,} samples — {best.get('n_train', '?'):,} train / {best.get('n_test', '?'):,} test)")
    lines.append(f"- **Cross-validation:** {cv_folds}-fold on training set")
    lines.append(f"- **Task type:** {task_category}\n")

    # Reusable Config
    lines.append("## Reusable Config\n")
    lines.append("Best model configuration for retraining:\n")
    config = {
        "model_type": best.get("model_type"),
        "model_class": best.get("model_display"),
        "dataset": dataset_name,
        "target": target,
        "n_samples": best.get("n_total"),
        "features": best.get("features"),
        "params": best.get("params"),
        "cv_folds": cv_folds,
        "primary_metric": best.get("primary_metric_name"),
        "primary_metric_value": best.get("primary_metric_value"),
    }
    lines.append(f"```json\n{json_mod.dumps(config, indent=2)}\n```\n")

    return "\n".join(lines)
