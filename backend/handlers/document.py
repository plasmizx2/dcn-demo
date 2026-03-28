"""Handler for document_analysis tasks."""

from ai.gemini_client import generate_text


def handle(task: dict, job: dict) -> str:
    """Analyze a document chunk using Gemini."""
    text = job.get("input_payload", {}).get("text", "")
    task_desc = task.get("task_description", "")

    if not text:
        # Fallback: use job title + task description
        text = f"{job.get('title', 'Untitled')} — {job.get('description', '')}"

    prompt = (
        f"You are analyzing a document. Your specific assignment: {task_desc}\n\n"
        f"Document text:\n{text}\n\n"
        f"Provide a clear, structured analysis with key points and insights."
    )

    return generate_text(prompt)
