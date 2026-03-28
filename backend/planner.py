"""
Planner module — splits a job into subtasks based on task_type.

Each task type has its own section so you can plug in real splitting
logic later (e.g. measure document size, scan codebase modules, etc.).
For now, each type returns 3 placeholder subtasks.
"""


def plan_tasks(task_type: str, input_payload: dict) -> list[dict]:
    """
    Given a task_type and the job's input_payload, return a list of subtask dicts.
    Each dict has: task_name, task_description, task_payload

    To add real logic later, edit the section for that task_type.
    """

    if task_type == "document_analysis":
        return _plan_document_analysis(input_payload)

    elif task_type == "codebase_review":
        return _plan_codebase_review(input_payload)

    elif task_type == "website_builder":
        return _plan_website_builder(input_payload)

    elif task_type == "research_pipeline":
        return _plan_research_pipeline(input_payload)

    elif task_type == "data_processing":
        return _plan_data_processing(input_payload)

    else:
        # Unknown task type — create 3 generic subtasks
        return [
            {"task_name": f"step_{i}", "task_description": f"Subtask {i} for {task_type}", "task_payload": {}}
            for i in range(1, 4)
        ]


# ──────────────────────────────────────────────
# Task-type-specific planners
# Each returns a list of subtask dicts.
# Replace placeholder logic with real splitting later.
# ──────────────────────────────────────────────


def _plan_document_analysis(input_payload: dict) -> list[dict]:
    """
    TODO: Later, inspect input_payload for document size and split
    into chunks accordingly. For now, always splits into 3 chunks.
    """
    return [
        {"task_name": "chunk_1_analysis", "task_description": "Analyze chunk 1 of the document (scope TBD by worker)", "task_payload": {}},
        {"task_name": "chunk_2_analysis", "task_description": "Analyze chunk 2 of the document (scope TBD by worker)", "task_payload": {}},
        {"task_name": "chunk_3_analysis", "task_description": "Analyze chunk 3 of the document (scope TBD by worker)", "task_payload": {}},
    ]


def _plan_codebase_review(input_payload: dict) -> list[dict]:
    """
    TODO: Later, scan the actual codebase and split by real modules/directories.
    For now, creates 3 generic sections.
    """
    return [
        {"task_name": "section_1_review", "task_description": "Review section 1 of the codebase (specific scope TBD by worker)", "task_payload": {}},
        {"task_name": "section_2_review", "task_description": "Review section 2 of the codebase (specific scope TBD by worker)", "task_payload": {}},
        {"task_name": "section_3_review", "task_description": "Review section 3 of the codebase (specific scope TBD by worker)", "task_payload": {}},
    ]


def _plan_website_builder(input_payload: dict) -> list[dict]:
    """
    TODO: Later, inspect input_payload for requested page sections.
    For now, creates 3 generic sections.
    """
    return [
        {"task_name": "section_1_build", "task_description": "Build section 1 of the website (specific scope TBD by worker)", "task_payload": {}},
        {"task_name": "section_2_build", "task_description": "Build section 2 of the website (specific scope TBD by worker)", "task_payload": {}},
        {"task_name": "section_3_build", "task_description": "Build section 3 of the website (specific scope TBD by worker)", "task_payload": {}},
    ]


def _plan_research_pipeline(input_payload: dict) -> list[dict]:
    """
    TODO: Later, break research into phases based on input_payload topic.
    For now, creates 3 generic phases.
    """
    return [
        {"task_name": "phase_1_research", "task_description": "Research phase 1 (specific scope TBD by worker)", "task_payload": {}},
        {"task_name": "phase_2_research", "task_description": "Research phase 2 (specific scope TBD by worker)", "task_payload": {}},
        {"task_name": "phase_3_research", "task_description": "Research phase 3 (specific scope TBD by worker)", "task_payload": {}},
    ]


def _plan_data_processing(input_payload: dict) -> list[dict]:
    """
    TODO: Later, split by actual data size or batch count.
    For now, always creates 3 batches.
    """
    return [
        {"task_name": "batch_1_processing", "task_description": "Process batch 1 of the data (scope TBD by worker)", "task_payload": {}},
        {"task_name": "batch_2_processing", "task_description": "Process batch 2 of the data (scope TBD by worker)", "task_payload": {}},
        {"task_name": "batch_3_processing", "task_description": "Process batch 3 of the data (scope TBD by worker)", "task_payload": {}},
    ]
