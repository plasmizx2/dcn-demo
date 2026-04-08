import json
import time
from typing import Any

import requests


OLLAMA_BASE = "http://localhost:11434"


def _backend_base(job: dict) -> str:
    # In the demo worker, BASE_URL is set in the worker process, but handlers don't see it.
    # So we read it from environment if present, else fall back to production.
    import os

    return os.getenv("DCN_BASE_URL") or os.getenv("BASE_URL") or "https://dcn-demo.onrender.com"


def _post_event(base_url: str, job_id: str, worker_node_id: str, event_type: str, message: str) -> None:
    try:
        requests.post(
            f"{base_url}/chat/worker/{job_id}/event",
            json={
                "worker_node_id": worker_node_id,
                "event_type": event_type,
                "message": message,
            },
            timeout=10,
        )
    except Exception:
        pass


def _start_assistant_message(base_url: str, job_id: str, worker_node_id: str) -> int:
    resp = requests.post(
        f"{base_url}/chat/worker/{job_id}/assistant/start",
        json={"worker_node_id": worker_node_id},
        timeout=10,
    )
    resp.raise_for_status()
    return int(resp.json()["seq"])


def _append_chunk(base_url: str, job_id: str, worker_node_id: str, seq: int, chunk: str) -> None:
    requests.post(
        f"{base_url}/chat/worker/{job_id}/assistant/chunk",
        json={"worker_node_id": worker_node_id, "seq": seq, "chunk": chunk},
        timeout=10,
    )


def _ollama_stream_chat(model: str, messages: list[dict[str, str]]) -> Any:
    """
    Yield assistant text chunks from Ollama /api/chat streaming responses.
    """
    r = requests.post(
        f"{OLLAMA_BASE}/api/chat",
        json={"model": model, "messages": messages, "stream": True},
        stream=True,
        timeout=120,
    )
    r.raise_for_status()
    for line in r.iter_lines(decode_unicode=True):
        if not line:
            continue
        try:
            data = json.loads(line)
        except Exception:
            continue
        if data.get("done"):
            break
        msg = data.get("message") or {}
        chunk = msg.get("content") or ""
        if chunk:
            yield chunk


def handle(task: dict, job: dict) -> str:
    """
    Long-running chat session handler.

    Contract:
    - Reads user messages from coordinator via /chat/{job_id}/messages polling.
    - Generates assistant responses locally (Ollama) and streams chunks back via worker endpoints.
    - Returns a short final transcript summary in result_text.
    """
    task_payload = task.get("task_payload") or {}
    if isinstance(task_payload, str):
        try:
            task_payload = json.loads(task_payload)
        except Exception:
            task_payload = {}

    job_id = str(task.get("job_id") or "")
    worker_node_id = str(task.get("worker_node_id") or "")
    base_url = _backend_base(job)

    model = str(task_payload.get("model") or "llama3.1")
    idle_timeout_seconds = int(task_payload.get("idle_timeout_seconds") or 300)
    max_duration_seconds = int(task_payload.get("max_duration_seconds") or 1800)
    system_prompt = (task_payload.get("system_prompt") or "").strip()

    conversation: list[dict[str, str]] = []
    if system_prompt:
        conversation.append({"role": "system", "content": system_prompt})

    _post_event(base_url, job_id, worker_node_id, "session_start", f"Chat session started (model={model})")

    start_ts = time.time()
    last_user_ts = time.time()
    last_seq = 0
    transcript_pairs: list[tuple[str, str]] = []

    # Poll loop: stop on max duration or idle timeout
    while True:
        now = time.time()
        if now - start_ts > max_duration_seconds:
            _post_event(base_url, job_id, worker_node_id, "session_end", "Max duration reached; ending session.")
            break
        if now - last_user_ts > idle_timeout_seconds:
            _post_event(base_url, job_id, worker_node_id, "session_end", "Idle timeout reached; ending session.")
            break

        # Pull any new messages
        try:
            resp = requests.get(
                f"{base_url}/chat/worker/{job_id}/messages",
                params={"after_seq": last_seq},
                timeout=15,
            )
            rows = resp.json() if resp.status_code == 200 else []
        except Exception:
            rows = []

        # Process all new user messages; ignore assistant/system rows (those were streamed by us)
        new_user = [r for r in rows if r.get("role") == "user"]
        if not new_user:
            time.sleep(1.0)
            continue

        for r in new_user:
            seq = int(r.get("seq") or 0)
            content = str(r.get("content") or "")
            if seq <= last_seq:
                continue
            last_seq = seq
            last_user_ts = time.time()

            conversation.append({"role": "user", "content": content})
            _post_event(base_url, job_id, worker_node_id, "user", f"User message seq={seq}")

            # Start assistant row and stream chunks into it.
            try:
                assistant_seq = _start_assistant_message(base_url, job_id, worker_node_id)
            except Exception as e:
                _post_event(base_url, job_id, worker_node_id, "error", f"Failed to start assistant message: {e}")
                return f"Chat failed to start assistant message: {e}"

            assistant_text = ""
            try:
                for chunk in _ollama_stream_chat(model=model, messages=conversation):
                    assistant_text += chunk
                    try:
                        _append_chunk(base_url, job_id, worker_node_id, assistant_seq, chunk)
                    except Exception:
                        # If streaming back fails, we still keep generating and end with a full result.
                        pass
                conversation.append({"role": "assistant", "content": assistant_text})
                transcript_pairs.append((content, assistant_text))
            except requests.RequestException as e:
                _post_event(base_url, job_id, worker_node_id, "error", f"Ollama error: {e}")
                return f"Ollama error: {e}"

        # Keep loop alive for more turns

    # Return a compact transcript for job result
    lines: list[str] = []
    lines.append("Local LLM chat session finished.")
    lines.append(f"- model: {model}")
    lines.append(f"- turns: {len(transcript_pairs)}")
    lines.append("")
    for i, (u, a) in enumerate(transcript_pairs[-5:], 1):
        lines.append(f"### Turn {i}")
        lines.append(f"User: {u}")
        lines.append("")
        lines.append(f"Assistant: {a}")
        lines.append("")

    return "\n".join(lines).strip()

