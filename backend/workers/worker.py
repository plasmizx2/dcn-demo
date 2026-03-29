"""
AI-powered worker loop for Step 8.

Usage:
    python workers/worker.py <worker_node_id>

Run 2-3 of these in separate terminals with different worker UUIDs.
"""

import sys
import os
import time
import json
import requests

# Add backend root to path so we can import handlers
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from handlers import document, codebase, website, research, data_processing, ml_experiment

BASE_URL = "http://localhost:8000"

# Map task_type -> handler
HANDLERS = {
    "document_analysis": document.handle,
    "codebase_review": codebase.handle,
    "website_builder": website.handle,
    "research_pipeline": research.handle,
    "data_processing": data_processing.handle,
    "ml_experiment": ml_experiment.handle,
}


def heartbeat(worker_node_id):
    resp = requests.post(
        f"{BASE_URL}/workers/heartbeat",
        json={"worker_node_id": worker_node_id},
    )
    if resp.status_code == 200:
        data = resp.json()
        print(f"[heartbeat] {data.get('node_name', worker_node_id)} alive")
    else:
        print(f"[heartbeat] failed: {resp.text}")


AI_TASK_TYPES = [
    "codebase_review", "document_analysis", "research_pipeline",
    "website_builder", "data_processing", "ml_experiment",
]


def claim_task(worker_node_id):
    resp = requests.post(
        f"{BASE_URL}/tasks/claim",
        json={"worker_node_id": worker_node_id, "task_types": AI_TASK_TYPES, "worker_tier": 4},
    )
    if resp.status_code == 200:
        return resp.json()
    else:
        print(f"[claim] error: {resp.text}")
        return None


def fetch_job(job_id):
    """Fetch the parent job to get task_type and input_payload."""
    resp = requests.get(f"{BASE_URL}/jobs/{job_id}")
    if resp.status_code == 200:
        job = resp.json()
        # Ensure input_payload is a dict (may come back as JSON string)
        if isinstance(job.get("input_payload"), str):
            try:
                job["input_payload"] = json.loads(job["input_payload"])
            except (json.JSONDecodeError, TypeError):
                job["input_payload"] = {}
        return job
    else:
        print(f"[job] error fetching job {job_id}: {resp.text}")
        return None


def complete_task(task_id, result_text, execution_time):
    resp = requests.post(
        f"{BASE_URL}/tasks/{task_id}/complete",
        json={
            "result_text": result_text,
            "execution_time_seconds": execution_time,
        },
    )
    if resp.status_code == 200:
        return resp.json()
    else:
        print(f"[complete] error: {resp.text}")
        return None


def fail_task(task_id):
    """Mark a task as failed via the API."""
    resp = requests.post(
        f"{BASE_URL}/tasks/{task_id}/fail",
    )
    if resp.status_code == 200:
        return resp.json()
    else:
        print(f"[fail] error: {resp.text}")
        return None


def process_task(task, job):
    """Run the appropriate handler based on task_type."""
    task_type = job.get("task_type", "")
    handler = HANDLERS.get(task_type)

    if not handler:
        return f"No handler for task type: {task_type}"

    return handler(task, job)


def run_worker(worker_node_id):
    print(f"=== AI Worker started: {worker_node_id} ===")
    print(f"    Polling {BASE_URL}")
    print()

    while True:
        # Send heartbeat
        heartbeat(worker_node_id)

        # Try to claim a task
        result = claim_task(worker_node_id)

        if result and result.get("claimed"):
            task = result["task"]
            task_id = task["id"]
            task_name = task.get("task_name", "unknown")
            job_id = task.get("job_id")

            print(f"[claimed] task {task_id} — {task_name}")

            # Fetch the parent job for task_type and input_payload
            job = fetch_job(job_id)
            if not job:
                print(f"[error] could not fetch job {job_id}, skipping")
                fail_task(task_id)
                continue

            task_type = job.get("task_type", "unknown")
            print(f"[processing] type={task_type}, calling handler...")

            # Ensure task_payload is a dict (may come back as JSON string)
            if isinstance(task.get("task_payload"), str):
                try:
                    task["task_payload"] = json.loads(task["task_payload"])
                except (json.JSONDecodeError, TypeError):
                    task["task_payload"] = {}

            # Process with AI — retry with backoff on failure
            start_time = time.time()
            retries = [5, 15, 30]  # seconds to wait between attempts
            succeeded = False

            for attempt in range(len(retries) + 1):
                try:
                    result_text = process_task(task, job)
                    execution_time = round(time.time() - start_time, 2)
                    print(f"[ai done] got {len(result_text)} chars in {execution_time}s")

                    complete_result = complete_task(task_id, result_text, execution_time)
                    if complete_result and complete_result.get("completed"):
                        print(f"[done] task {task_id} submitted")
                        if complete_result.get("job_aggregated"):
                            print(f"[aggregated] job {job_id} final output ready!")
                    else:
                        print(f"[error] failed to submit task {task_id}")

                    succeeded = True
                    break

                except Exception as e:
                    error_str = str(e).lower()
                    is_rate_limit = "429" in str(e) or "rate" in error_str or "quota" in error_str
                    execution_time = round(time.time() - start_time, 2)

                    if attempt < len(retries):
                        wait = retries[attempt]
                        if is_rate_limit:
                            wait = wait * 2  # extra backoff for rate limits
                            print(f"[rate limit] hit rate limit, waiting {wait}s...")
                        else:
                            print(f"[ai error] {e} — retrying in {wait}s...")
                        time.sleep(wait)
                    else:
                        print(f"[failed] all retries exhausted: {e}")

            if not succeeded:
                fail_task(task_id)

            print()
        else:
            msg = result.get("message", "No response") if result else "Request failed"
            print(f"[idle] {msg} — waiting 5s")
            time.sleep(5)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python workers/worker.py <worker_node_id>")
        print("  worker_node_id = UUID from your worker_nodes table")
        sys.exit(1)

    run_worker(sys.argv[1])
