"""Handler for website_builder tasks."""

from ai.gemini_client import generate_text


def handle(task: dict, job: dict) -> str:
    """Generate a website section using Gemini."""
    task_payload = task.get("task_payload", {})
    task_desc = task.get("task_description", "")

    prompt_input = job.get("input_payload", {}).get("prompt", "")
    if not prompt_input:
        prompt_input = f"{job.get('title', 'Untitled')} — {job.get('description', '')}"

    section_type = task_payload.get("section_type", "")
    section_order = task_payload.get("section_order", 0)
    total_sections = task_payload.get("total_sections", 0)

    order_context = ""
    if section_order and total_sections:
        order_context = (
            f"This is section {section_order} of {total_sections} in the page. "
            f"Ensure visual consistency with the other sections.\n"
        )

    prompt = (
        f"You are building a website. Your specific assignment: {task_desc}\n\n"
        f"{order_context}"
        f"Website description: {prompt_input}\n\n"
        f"Generate clean, modern HTML and CSS for this section. "
        f"Use a professional design with good spacing and typography. "
        f"Return only the HTML code for this section."
    )

    return generate_text(prompt)
