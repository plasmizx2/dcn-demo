"""Handler for document_analysis tasks."""

from ai.gemini_client import generate_text


def handle(task: dict, job: dict) -> str:
    """Analyze a document chunk using Gemini."""
    task_payload = task.get("task_payload", {})
    task_desc = task.get("task_description", "")

    # Prefer the specific text chunk assigned by the planner,
    # fall back to the full document text from the job
    text = task_payload.get("text_chunk", "")
    if not text:
        text = job.get("input_payload", {}).get("text", "")
    if not text:
        text = f"{job.get('title', 'Untitled')} — {job.get('description', '')}"

    chunk_info = ""
    if task_payload.get("chunk_index"):
        chunk_info = (
            f"You are analyzing section {task_payload['chunk_index']} "
            f"of {task_payload['total_chunks']} from this document.\n"
        )

    prompt = (
        f"You are analyzing a document. Your specific assignment: {task_desc}\n\n"
        f"{chunk_info}"
        f"Document text:\n{text}\n\n"
        f"Provide a clear, structured analysis with key points and insights."
    )

    return generate_text(prompt)
