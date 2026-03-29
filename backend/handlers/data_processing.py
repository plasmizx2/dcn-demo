"""Handler for data_processing tasks."""

from ai.gemini_client import generate_text


def handle(task: dict, job: dict) -> str:
    """Analyze and classify data using Gemini."""
    task_payload = task.get("task_payload", {})
    task_desc = task.get("task_description", "")

    # Prefer the specific data batch from the planner,
    # fall back to the full dataset from the job
    data = task_payload.get("data_batch", "")
    if not data:
        data = job.get("input_payload", {}).get("data", "")
    if not data:
        data = f"{job.get('title', 'Untitled')} — {job.get('description', '')}"

    batch_context = ""
    if task_payload.get("batch_index"):
        batch_context = (
            f"Processing batch {task_payload['batch_index']} of "
            f"{task_payload['total_batches']} "
            f"({task_payload.get('batch_record_count', '?')} records in this batch).\n"
        )

    prompt = (
        f"You are processing data. Your specific assignment: {task_desc}\n\n"
        f"{batch_context}"
        f"Data:\n{data}\n\n"
        f"Analyze and classify this data. Provide:\n"
        f"- Summary of the data\n"
        f"- Key patterns or categories found\n"
        f"- Any anomalies or notable observations\n"
        f"- Structured output of your classification"
    )

    return generate_text(prompt)
