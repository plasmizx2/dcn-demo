"""Handler for research_pipeline tasks."""

from ai.gemini_client import generate_text


def handle(task: dict, job: dict) -> str:
    """Perform a research phase using Gemini."""
    task_payload = task.get("task_payload", {})
    task_desc = task.get("task_description", "")

    # Prefer topic from task_payload (set by planner), fall back to job
    topic = task_payload.get("topic", "")
    if not topic:
        topic = job.get("input_payload", {}).get("topic", "")
    if not topic:
        topic = f"{job.get('title', 'Untitled')} — {job.get('description', '')}"

    phase = task_payload.get("research_phase", "general")
    phase_context = f"Research phase: {phase.upper()}\n" if phase != "general" else ""

    prompt = (
        f"You are conducting research on: {topic}\n"
        f"{phase_context}"
        f"Your specific assignment: {task_desc}\n\n"
        f"Provide structured research insights including:\n"
        f"- Key findings\n"
        f"- Important data points\n"
        f"- Notable sources or references\n"
        f"- Actionable takeaways\n\n"
        f"Be thorough but concise."
    )

    return generate_text(prompt)
