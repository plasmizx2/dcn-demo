"""
Shared utilities for DCN backend.

Reduces code duplication across handlers and API modules.
"""

import json
import logging
from typing import Any

logger = logging.getLogger("dcn.utils")


def safe_json_parse(value: Any) -> dict:
    """Parse a JSON string to dict. Returns {} on failure or non-string input."""
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            result = json.loads(value)
            return result if isinstance(result, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


def get_input_text(job: dict, key: str = "text") -> str:
    """Extract input text from a job's input_payload, handling str/dict payloads."""
    payload = job.get("input_payload", {})
    if isinstance(payload, str):
        payload = safe_json_parse(payload)
    return payload.get(key, "")


def get_task_payload(task: dict) -> dict:
    """Extract task_payload from a task, handling str/dict payloads."""
    payload = task.get("task_payload", {})
    if isinstance(payload, str):
        return safe_json_parse(payload)
    return payload if isinstance(payload, dict) else {}


def make_handler_prompt(
    role: str,
    task_desc: str,
    context: str,
    instructions: str,
) -> str:
    """Build a standardized prompt for Gemini-based handlers.

    Args:
        role: The persona for the AI (e.g., "senior code reviewer")
        task_desc: What the task is about
        context: The input data/content to analyze
        instructions: Specific output format instructions
    """
    return (
        f"You are a {role}.\n\n"
        f"Task: {task_desc}\n\n"
        f"Context/Input:\n{context}\n\n"
        f"Instructions: {instructions}"
    )


def clamp(value: float, min_val: float, max_val: float) -> float:
    """Clamp a numeric value to [min_val, max_val]."""
    return max(min_val, min(max_val, value))
