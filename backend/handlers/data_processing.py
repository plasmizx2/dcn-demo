"""Handler for data_processing tasks."""

from ai.gemini_client import generate_text


def handle(task: dict, job: dict) -> str:
    """Analyze and classify data using Gemini."""
    data = job.get("input_payload", {}).get("data", "")
    task_desc = task.get("task_description", "")

    if not data:
        data = f"{job.get('title', 'Untitled')} — {job.get('description', '')}"

    prompt = (
        f"You are processing data. Your specific assignment: {task_desc}\n\n"
        f"Data:\n{data}\n\n"
        f"Analyze and classify this data. Provide:\n"
        f"- Summary of the data\n"
        f"- Key patterns or categories found\n"
        f"- Any anomalies or notable observations\n"
        f"- Structured output of your classification"
    )

    return generate_text(prompt)
