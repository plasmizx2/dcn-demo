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
