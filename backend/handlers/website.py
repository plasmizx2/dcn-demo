"""Handler for website_builder tasks."""

from ai.gemini_client import generate_text


def handle(task: dict, job: dict) -> str:
    """Generate a website section using Gemini."""
    prompt_input = job.get("input_payload", {}).get("prompt", "")
    task_desc = task.get("task_description", "")

    if not prompt_input:
        prompt_input = f"{job.get('title', 'Untitled')} — {job.get('description', '')}"

    prompt = (
        f"You are building a website. Your specific assignment: {task_desc}\n\n"
        f"Website description: {prompt_input}\n\n"
        f"Generate clean, modern HTML and CSS for this section. "
        f"Use a professional design with good spacing and typography. "
        f"Return only the HTML code for this section."
    )

    return generate_text(prompt)
