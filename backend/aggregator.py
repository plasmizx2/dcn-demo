"""
Step 9 — Aggregation: combine task results into a final job output.

Uses Gemini synthesis for task types that benefit from it,
simple concatenation for everything else.
"""

import asyncio
from ai.gemini_client import generate_text

# Task types that just get concatenated (no Gemini call)
CONCAT_TYPES = {
    "codebase_review", "website_builder", "data_processing",
    "image_processing", "web_scraping", "audio_transcription",
    "sentiment_classification",
}


async def aggregate_job(conn, job_id: str):
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

    task_type = job["task_type"]

    if task_type == "ml_experiment":
        try:
            final_output = _aggregate_ml_experiment(results, job)
        except Exception as e:
            print(f"[aggregator] ML experiment aggregation failed ({e}), falling back")
            final_output = concatenate_results(results, task_type)
    elif task_type in CONCAT_TYPES:
        final_output = concatenate_results(results, task_type)
    else:
        try:
            final_output = await asyncio.to_thread(synthesize_results, results, job)
        except Exception as e:
            print(f"[aggregator] Gemini synthesis failed ({e}), falling back to concatenation")
            final_output = concatenate_results(results, task_type)

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

    return True


def concatenate_results(results, task_type: str) -> str:
    """Smart concatenation — merges batch results into one clean report."""

    # For distributed worker types, strip repeated headings and merge cleanly
    DISTRIBUTED_TYPES = {
        "image_processing", "web_scraping", "audio_transcription", "sentiment_classification",
    }

    if task_type in DISTRIBUTED_TYPES:
        return _merge_distributed_results(results, task_type)

    # For AI types, keep section headers
    sections = []
    for r in results:
        sections.append(
            f"=== {r['task_name']} ===\n\n{r['result_text']}"
        )
    return "\n\n---\n\n".join(sections)


def _merge_distributed_results(results, task_type: str) -> str:
    """Merge distributed batch results into a single clean report."""
    import re

    # Heading patterns each handler uses
    HEADING_PATTERNS = {
        "image_processing": r"^## Image Processing Results?\s*\n+",
        "web_scraping": r"^## Web Scraping Results?\s*\n+",
        "audio_transcription": r"^## Transcription Results?\s*\n+",
        "sentiment_classification": r"^## Sentiment Classification Results?\s*\n+",
    }

    TITLES = {
        "image_processing": "## Image Processing Results\n\n",
        "web_scraping": "## Web Scraping Results\n\n",
        "audio_transcription": "## Transcription Results\n\n",
        "sentiment_classification": "## Sentiment Classification Results\n\n",
    }

    heading_re = HEADING_PATTERNS.get(task_type, "")
    title = TITLES.get(task_type, f"## {task_type.replace('_', ' ').title()} Results\n\n")

    cleaned_sections = []
    total_items = 0

    for r in results:
        text = (r["result_text"] or "").strip()

        # Strip the repeated heading
        if heading_re:
            text = re.sub(heading_re, "", text, count=1).strip()

        # Strip the "Processed N items..." / "Scraped N URLs" / "Analyzed N items" summary line
        text = re.sub(r"^(Processed|Scraped|Transcribed|Analyzed)\s+\d+\s+\S+.*\n*", "", text, count=1).strip()

        # Count items from summary lines for a combined total
        summary_match = re.search(r"(\d+)\s+(images?|URLs?|files?|items?)", r["result_text"] or "")
        if summary_match:
            total_items += int(summary_match.group(1))

        if text:
            cleaned_sections.append(text)

    # For sentiment, merge the summary counts and only keep detailed results
    if task_type == "sentiment_classification":
        return _merge_sentiment(results, title, total_items, len(results))

    # Build combined summary line
    item_word = {
        "image_processing": "images",
        "web_scraping": "URLs",
        "audio_transcription": "audio files",
    }.get(task_type, "items")

    summary = f"Processed {total_items} {item_word} across {len(results)} workers\n\n" if total_items else ""

    return title + summary + "\n\n---\n\n".join(cleaned_sections)


def _merge_sentiment(results, title, total_items, num_workers):
    """Merge sentiment batches: combine counts into one summary + all details."""
    import re

    pos = neg = neu = 0
    all_details = []

    for r in results:
        text = (r["result_text"] or "").strip()

        # Extract counts from each batch
        pos_match = re.search(r"\*\*Positive:\*\*\s*(\d+)", text)
        neg_match = re.search(r"\*\*Negative:\*\*\s*(\d+)", text)
        neu_match = re.search(r"\*\*Neutral:\*\*\s*(\d+)", text)

        if pos_match:
            pos += int(pos_match.group(1))
        if neg_match:
            neg += int(neg_match.group(1))
        if neu_match:
            neu += int(neu_match.group(1))

        # Extract only the detailed results section
        detail_match = re.search(r"### Detailed Results\s*\n+(.*)", text, re.DOTALL)
        if detail_match:
            detail_text = detail_match.group(1).strip()
        else:
            # Fallback: strip everything above the numbered results
            detail_text = re.sub(r"^##.*?\n", "", text, flags=re.MULTILINE)
            detail_text = re.sub(r"^-\s*\*\*\w+:\*\*.*\n?", "", detail_text, flags=re.MULTILINE)
            detail_text = re.sub(r"^### Summary\s*\n?", "", detail_text)
            detail_text = detail_text.strip()

        if detail_text:
            # Strip LLM preamble lines like "Here are the classifications:"
            detail_text = re.sub(r"^(Here are the classifications[:\.]?\s*\n*)", "", detail_text, flags=re.IGNORECASE)
            detail_text = re.sub(r"^(Here is the classification[:\.]?\s*\n*)", "", detail_text, flags=re.IGNORECASE)
            detail_text = re.sub(r"^(Here are the results[:\.]?\s*\n*)", "", detail_text, flags=re.IGNORECASE)
            detail_text = detail_text.strip()
            if detail_text:
                all_details.append(detail_text)

    total = pos + neg + neu or total_items or 1

    return (
        f"{title}"
        f"Analyzed {total_items or total} items across {num_workers} workers\n\n"
        f"### Summary\n"
        f"- **Positive:** {pos} ({round(pos/total*100)}%)\n"
        f"- **Negative:** {neg} ({round(neg/total*100)}%)\n"
        f"- **Neutral:** {neu} ({round(neu/total*100)}%)\n\n"
        f"### Detailed Results\n\n"
        + "\n\n".join(all_details) + "\n"
    )


def synthesize_results(results, job) -> str:
    """Use Gemini to combine subtask results into a coherent final report."""
    combined = "\n\n---\n\n".join(
        f"[{r['task_name']}]\n{r['result_text']}" for r in results
    )

    prompt = (
        f"You are combining subtask results into one final report.\n"
        f"Job: {job['title']}\n"
        f"Type: {job['task_type']}\n\n"
        f"Subtask results:\n\n{combined}\n\n"
        f"Combine these into a single coherent report. "
        f"Keep all important details. Be concise but thorough."
    )

    return generate_text(prompt)


def _aggregate_ml_experiment(results, job) -> str:
    """
    Custom aggregation for ml_experiment: parse JSON metrics from each
    experiment result, rank them, and produce a structured comparison report.
    Now includes CV scores, compute time breakdown, and more metrics.
    """
    import re
    import json as json_mod

    experiments = []

    for r in results:
        text = r["result_text"] or ""

        # Extract the JSON block embedded in each result
        json_match = re.search(r'```json\s*\n(\{.*?\})\s*\n```', text, re.DOTALL)
        if json_match:
            try:
                data = json_mod.loads(json_match.group(1))
                experiments.append(data)
            except json_mod.JSONDecodeError:
                pass

    if not experiments:
        return concatenate_results(results, "ml_experiment")

    task_category = experiments[0].get("task_category", "regression")

    if task_category == "regression":
        experiments.sort(key=lambda x: x.get("r2", 0), reverse=True)
        primary_metric = "R²"
    else:
        experiments.sort(key=lambda x: x.get("f1", 0), reverse=True)
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
