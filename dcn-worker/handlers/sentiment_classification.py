"""
Sentiment classification handler — classify text using local Ollama LLM.
Requires: Ollama installed with llama3.2 model.
"""

import json
import subprocess
import time


def _query_ollama(prompt, model="llama3.2"):
    """Send a prompt to Ollama and return the response text."""
    result = subprocess.run(
        ["ollama", "run", model],
        input=prompt,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Ollama error: {result.stderr}")
    return result.stdout.strip()


def handle(task, job):
    """Classify sentiment of text items using local Ollama."""
    payload = task.get("task_payload") or {}
    job_payload = job.get("input_payload") or {}

    texts = payload.get("texts") or job_payload.get("texts", [])

    # If single text provided, treat as one item
    if not texts:
        single = job_payload.get("text", "")
        if single:
            texts = [single]

    if not texts:
        return (
            "## Sentiment Classification Report\n\n"
            "No text items provided. In production, this worker would:\n"
            "- Receive batches of text (reviews, comments, feedback)\n"
            "- Classify each as positive, negative, or neutral\n"
            "- Extract key topics and themes\n"
            "- Return structured results\n\n"
            "**Model:** llama3.2 via Ollama (runs locally)\n"
        )

    results = []
    counts = {"positive": 0, "negative": 0, "neutral": 0}
    start = time.time()

    # Process in a single batch prompt for efficiency
    batch_text = "\n".join(f"{i+1}. {t[:200]}" for i, t in enumerate(texts))

    prompt = (
        "Classify the sentiment of each item below as POSITIVE, NEGATIVE, or NEUTRAL. "
        "For each item, respond with the number, sentiment, and a brief reason (one line each).\n\n"
        f"{batch_text}\n\n"
        "Format each line as: NUMBER. SENTIMENT — reason"
    )

    try:
        response = _query_ollama(prompt)
        elapsed = round(time.time() - start, 2)

        # Count sentiments from response
        for line in response.split("\n"):
            lower = line.lower()
            if "positive" in lower:
                counts["positive"] += 1
            elif "negative" in lower:
                counts["negative"] += 1
            elif "neutral" in lower:
                counts["neutral"] += 1

        total = sum(counts.values()) or len(texts)
        return (
            f"## Sentiment Classification Results\n\n"
            f"Analyzed {len(texts)} items in {elapsed}s\n\n"
            f"### Summary\n"
            f"- **Positive:** {counts['positive']} ({round(counts['positive']/total*100)}%)\n"
            f"- **Negative:** {counts['negative']} ({round(counts['negative']/total*100)}%)\n"
            f"- **Neutral:** {counts['neutral']} ({round(counts['neutral']/total*100)}%)\n\n"
            f"### Detailed Results\n\n{response}\n"
        )

    except Exception as e:
        return (
            f"## Sentiment Classification\n\n"
            f"**Error:** {e}\n\n"
            f"Items to classify: {len(texts)}\n"
        )
