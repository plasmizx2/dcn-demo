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
import logging
import traceback
import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("dcn.worker")

# Add backend root to path so we can import handlers
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from handlers import ml_experiment
from config import RETRY_BACKOFF_SECONDS, RATE_LIMIT_BACKOFF_MULTIPLIER, WORKER_POLL_INTERVAL_SECONDS

BASE_URL = os.getenv("DCN_BASE_URL", "https://dcn-demo.onrender.com")

# Tell Gemini client where to find the cache server
os.environ["DCN_CACHE_URL"] = BASE_URL


def detect_worker_tier():
    """
    Determine this machine's capability tier based on actual hardware.

    Tier 1: minimal (< 4 cores OR < 4 GB RAM)
    Tier 2: standard (4+ cores, 4+ GB RAM)
    Tier 3: capable (6+ cores, 8+ GB RAM)
    Tier 4: heavy   (8+ cores, 16+ GB RAM)
    """
    import os

    cores = os.cpu_count() or 1

    ram_gb = None
    try:
        import psutil
        ram_gb = psutil.virtual_memory().total / (1024 ** 3)
    except ImportError:
        # No psutil — try reading /proc/meminfo (Linux)
        try:
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        kb = int(line.split()[1])
                        ram_gb = kb / (1024 ** 2)
                        break
        except (FileNotFoundError, ValueError):
            ram_gb = 4  # safe fallback

    if ram_gb is None:
        ram_gb = 4

    # Check for GPU
    has_gpu = False
    import shutil, subprocess, platform
    if shutil.which("nvidia-smi"):
        has_gpu = True
    elif platform.system() == "Windows":
        try:
            result = subprocess.run(
                ["powershell.exe", "-Command",
                 "Get-CimInstance -ClassName Win32_VideoController | Select-Object -ExpandProperty Name"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    if any(kw in line.strip().lower() for kw in ["radeon", "geforce", "nvidia", "amd", "rtx", "gtx", "rx "]):
                        has_gpu = True
                        break
        except Exception:
            pass

    # Determine tier
    if cores >= 8 and ram_gb >= 16:
        tier = 4
    elif has_gpu or (cores >= 6 and ram_gb >= 8):
        tier = 3
    elif cores >= 4 and ram_gb >= 4:
        tier = 2
    else:
        tier = 1

    gpu_str = "detected" if has_gpu else "none"
    logger.info("Hardware: cores=%d, ram=%.1fGB, gpu=%s → tier %d", cores, ram_gb, gpu_str, tier)
    return tier


WORKER_TIER = detect_worker_tier()

# Map task_type -> handler
HANDLERS = {
    "ml_experiment": ml_experiment.handle,
}


def heartbeat(worker_node_id):
    resp = requests.post(
        f"{BASE_URL}/workers/heartbeat",
        json={"worker_node_id": worker_node_id},
    )
    if resp.status_code == 200:
        data = resp.json()
        logger.info("Heartbeat: %s alive", data.get('node_name', worker_node_id))
    else:
        logger.warning("Heartbeat failed: %s", resp.text)


AI_TASK_TYPES = [
    "ml_experiment",
]


def claim_task(worker_node_id):
    resp = requests.post(
        f"{BASE_URL}/tasks/claim",
        json={"worker_node_id": worker_node_id, "task_types": AI_TASK_TYPES, "worker_tier": WORKER_TIER},
    )
    if resp.status_code == 200:
        return resp.json()
    else:
        logger.error("Claim error: %s", resp.text)
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
        logger.error("Failed to fetch job %s: %s", job_id, resp.text)
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
    logger.error("Failed to submit task %s: %s", task_id, resp.text)
    raise RuntimeError(
        f"POST /complete failed HTTP {resp.status_code}: {resp.text[:800]}"
    )


def fail_task(task_id, error=None):
    """Mark a task as failed via the API; optional error text is stored for /ops event feed."""
    payload = {}
    if error and str(error).strip():
        payload["error"] = str(error).strip()[:8000]
    resp = requests.post(
        f"{BASE_URL}/tasks/{task_id}/fail",
        json=payload,
    )
    if resp.status_code == 200:
        return resp.json()
    else:
        logger.error("Failed to mark task %s as failed: %s", task_id, resp.text)
        return None


def process_task(task, job):
    """Run the appropriate handler based on task_type."""
    task_type = job.get("task_type", "")
    handler = HANDLERS.get(task_type)

    if not handler:
        return f"No handler for task type: {task_type}"

    return handler(task, job)


def run_worker(worker_node_id):
    logger.info("=== AI Worker started: %s ===", worker_node_id)
    logger.info("    Polling %s", BASE_URL)
    logger.info("    Tier: %d (cores=%s)", WORKER_TIER, os.cpu_count())

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

            logger.info("Claimed task %s — %s", task_id, task_name)

            # Fetch the parent job for task_type and input_payload
            job = fetch_job(job_id)
            if not job:
                logger.error("Could not fetch job %s, skipping", job_id)
                fail_task(
                    task_id,
                    error=f"fetch_job failed for job_id={job_id} (check BASE_URL / network)",
                )
                continue

            task_type = job.get("task_type", "unknown")
            logger.info("Processing type=%s, calling handler...", task_type)

            # Ensure task_payload is a dict (may come back as JSON string)
            if isinstance(task.get("task_payload"), str):
                try:
                    task["task_payload"] = json.loads(task["task_payload"])
                except (json.JSONDecodeError, TypeError):
                    task["task_payload"] = {}

            # Process with AI — retry with backoff on failure
            start_time = time.time()
            retries = RETRY_BACKOFF_SECONDS
            succeeded = False
            last_tb = None

            for attempt in range(len(retries) + 1):
                try:
                    result_text = process_task(task, job)
                    execution_time = round(time.time() - start_time, 2)
                    logger.info("Handler done: %d chars in %ss", len(result_text), execution_time)

                    complete_result = complete_task(task_id, result_text, execution_time)
                    if complete_result and complete_result.get("completed"):
                        logger.info("Task %s submitted", task_id)
                        if complete_result.get("job_aggregated"):
                            logger.info("Job %s aggregated — final output ready!", job_id)
                        succeeded = True
                        break
                    logger.error("Unexpected complete response for task %s: %s", task_id, complete_result)
                    raise RuntimeError("complete_task did not return completed=true")

                except Exception as e:
                    last_tb = traceback.format_exc()
                    error_str = str(e).lower()
                    is_rate_limit = "429" in str(e) or "rate" in error_str or "quota" in error_str

                    if attempt < len(retries):
                        wait = retries[attempt]
                        if is_rate_limit:
                            wait = wait * RATE_LIMIT_BACKOFF_MULTIPLIER
                            logger.warning("Rate limit hit, waiting %ds...", wait)
                        else:
                            logger.warning("Handler error: %s — retrying in %ds", e, wait)
                        time.sleep(wait)
                    else:
                        logger.error("All retries exhausted: %s", e)

            if not succeeded:
                fail_task(task_id, error=last_tb or "Task failed with no exception traceback")

            logger.debug("")
        else:
            msg = result.get("message", "No response") if result else "Request failed"
            logger.debug("Idle: %s — waiting %ds", msg, WORKER_POLL_INTERVAL_SECONDS)
            time.sleep(WORKER_POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        logger.error("Usage: python workers/worker.py <worker_node_id>")
        logger.error("  worker_node_id = UUID from your worker_nodes table")
        sys.exit(1)

    run_worker(sys.argv[1])
