"""
Step 9 — Aggregation: combine task results into a final job output.

Uses Gemini synthesis for task types that benefit from it,
simple concatenation for everything else.
"""

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
    # Count total vs submitted tasks
    counts = await conn.fetchrow(
        """
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE status = 'submitted') AS done
        FROM job_tasks
        WHERE job_id = $1
        """,
        job_id,
    )

    if counts["done"] < counts["total"]:
        return False

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

    if task_type in CONCAT_TYPES:
        final_output = concatenate_results(results, task_type)
    else:
        try:
            final_output = synthesize_results(results, job)
        except Exception as e:
            print(f"[aggregator] Gemini synthesis failed ({e}), falling back to concatenation")
            final_output = concatenate_results(results, task_type)

    # Update job with final output and status
    await conn.execute(
        """
        UPDATE jobs
        SET final_output = $1, status = 'completed'
        WHERE id = $2
        """,
        final_output,
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
    """Simple structured concatenation — keeps all detail intact."""
    sections = []
    for r in results:
        sections.append(
            f"=== {r['task_name']} ===\n\n{r['result_text']}"
        )
    return "\n\n---\n\n".join(sections)


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
