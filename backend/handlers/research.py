"""Handler for research_pipeline tasks."""

from ai.gemini_client import generate_text


def handle(task: dict, job: dict) -> str:
    """Perform a research phase using Gemini."""
    topic = job.get("input_payload", {}).get("topic", "")
    task_desc = task.get("task_description", "")

    if not topic:
        topic = f"{job.get('title', 'Untitled')} — {job.get('description', '')}"

    prompt = (
        f"You are conducting research on: {topic}\n"
        f"Your specific assignment: {task_desc}\n\n"
        f"Provide structured research insights including:\n"
        f"- Key findings\n"
        f"- Important data points\n"
        f"- Notable sources or references\n"
        f"- Actionable takeaways\n\n"
        f"Be thorough but concise."
    )

    return generate_text(prompt)
