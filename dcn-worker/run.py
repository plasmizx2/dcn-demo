#!/usr/bin/env python3
"""
DCN Distributed Worker — Join the network and earn by processing tasks.

Usage:
    python run.py                    # auto-detect everything
    python run.py --name MyLaptop   # set a custom worker name
"""

import os
import sys
import json
import time
import socket
import argparse
import requests

import hardware
import installer
from handlers import image_processing, web_scraping

# These are lazy-loaded based on tier
audio_handler = None
sentiment_handler = None

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")
STATE_FILE = os.path.join(os.path.dirname(__file__), ".worker_state.json")


def load_config():
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {}


def register_worker(server_url, name, capabilities):
    """Register this worker with the DCN server. Returns worker UUID."""
    print(f"[register] Registering as '{name}'...")
    resp = requests.post(
        f"{server_url}/workers/register",
        json={"node_name": name, "capabilities": capabilities},
        timeout=10,
    )
    if resp.status_code == 200:
        data = resp.json()
        print(f"[register] Registered! ID: {data['id']}")
        return data["id"]
    else:
        print(f"[register] Failed: {resp.text}")
        sys.exit(1)


def heartbeat(server_url, worker_id):
    try:
        resp = requests.post(
            f"{server_url}/workers/heartbeat",
            json={"worker_node_id": worker_id},
            timeout=5,
        )
        if resp.status_code == 200:
            return True
    except Exception:
        pass
    return False


def claim_task(server_url, worker_id, task_types):
    try:
        resp = requests.post(
            f"{server_url}/tasks/claim",
            json={"worker_node_id": worker_id, "task_types": task_types},
            timeout=10,
        )
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print(f"[claim] Error: {e}")
    return None


def fetch_job(server_url, job_id):
    try:
        resp = requests.get(f"{server_url}/jobs/{job_id}", timeout=10)
        if resp.status_code == 200:
            job = resp.json()
            if isinstance(job.get("input_payload"), str):
                try:
                    job["input_payload"] = json.loads(job["input_payload"])
                except (json.JSONDecodeError, TypeError):
                    job["input_payload"] = {}
            return job
    except Exception as e:
        print(f"[job] Error fetching job {job_id}: {e}")
    return None


def complete_task(server_url, task_id, result_text, execution_time):
    try:
        resp = requests.post(
            f"{server_url}/tasks/{task_id}/complete",
            json={"result_text": result_text, "execution_time_seconds": execution_time},
            timeout=30,
        )
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print(f"[complete] Error: {e}")
    return None


def fail_task(server_url, task_id):
    try:
        requests.post(f"{server_url}/tasks/{task_id}/fail", timeout=10)
    except Exception:
        pass


def get_handler(task_type):
    """Return the handler function for a task type."""
    global audio_handler, sentiment_handler

    if task_type == "image_processing":
        return image_processing.handle
    elif task_type == "web_scraping":
        return web_scraping.handle
    elif task_type == "audio_transcription":
        if audio_handler is None:
            from handlers import audio_transcription
            audio_handler = audio_transcription.handle
        return audio_handler
    elif task_type == "sentiment_classification":
        if sentiment_handler is None:
            from handlers import sentiment_classification
            sentiment_handler = sentiment_classification.handle
        return sentiment_handler
    return None


def run(server_url, worker_id, task_types):
    """Main worker loop."""
    tasks_completed = 0
    total_earnings = 0.0

    print(f"\n[worker] Listening for tasks: {', '.join(task_types)}")
    print(f"[worker] Server: {server_url}")
    print(f"[worker] Press Ctrl+C to stop\n")

    while True:
        # Heartbeat
        if not heartbeat(server_url, worker_id):
            print("[worker] Server unreachable, retrying in 10s...")
            time.sleep(10)
            continue

        # Try to claim a task
        result = claim_task(server_url, worker_id, task_types)

        if result and result.get("claimed"):
            task = result["task"]
            task_id = task["id"]
            task_name = task.get("task_name", "unknown")
            job_id = task.get("job_id")

            print(f"[claimed] Task: {task_name} ({task_id[:8]})")

            # Fetch parent job
            job = fetch_job(server_url, job_id)
            if not job:
                print(f"[error] Could not fetch job {job_id}")
                fail_task(server_url, task_id)
                continue

            task_type = job.get("task_type", "")
            handler = get_handler(task_type)

            if not handler:
                print(f"[error] No handler for type: {task_type}")
                fail_task(server_url, task_id)
                continue

            # Parse task_payload if it's a string
            if isinstance(task.get("task_payload"), str):
                try:
                    task["task_payload"] = json.loads(task["task_payload"])
                except (json.JSONDecodeError, TypeError):
                    task["task_payload"] = {}

            # Process
            print(f"[processing] Type: {task_type}...")
            start_time = time.time()

            try:
                result_text = handler(task, job)
                execution_time = round(time.time() - start_time, 2)
                print(f"[done] {len(result_text)} chars in {execution_time}s")

                comp = complete_task(server_url, task_id, result_text, execution_time)
                if comp and comp.get("completed"):
                    tasks_completed += 1
                    reward = job.get("reward_amount", 0) or 0
                    total_earnings += reward / 3  # split across tasks
                    print(f"[submitted] Task {task_id[:8]} complete")
                    if comp.get("job_aggregated"):
                        print(f"[aggregated] Job {job_id[:8]} finished!")
                    print(f"[stats] Tasks: {tasks_completed} | Earnings: ${total_earnings:.2f}")

            except Exception as e:
                print(f"[failed] {e}")
                fail_task(server_url, task_id)

            print()
        else:
            msg = result.get("message", "") if result else "No response"
            print(f"[idle] {msg} — waiting 5s")
            time.sleep(5)


def main():
    parser = argparse.ArgumentParser(description="DCN Distributed Worker")
    parser.add_argument("--name", type=str, help="Worker name (default: hostname)")
    parser.add_argument("--server", type=str, help="Server URL override")
    args = parser.parse_args()

    print()
    print("  ██████╗  ██████╗███╗   ██╗")
    print("  ██╔══██╗██╔════╝████╗  ██║")
    print("  ██║  ██║██║     ██╔██╗ ██║")
    print("  ██║  ██║██║     ██║╚██╗██║")
    print("  ██████╔╝╚██████╗██║ ╚████║")
    print("  ╚═════╝  ╚═════╝╚═╝  ╚═══╝")
    print("  Distributed Computation Network — Worker Node")
    print()

    # Load config
    config = load_config()
    server_url = args.server or config.get("server_url", "http://localhost:8000")
    worker_name = args.name or config.get("worker_name") or f"{socket.gethostname()}-worker"

    # Detect hardware
    hw = hardware.detect()
    hardware.print_report(hw)

    tier = hw["tier"]
    task_types = hw["supported_task_types"]

    # Install dependencies based on tier
    installer.setup_dependencies(tier)

    # Re-check task types after install (in case something failed)
    # For now, trust the tier detection

    # Check for existing registration
    state = load_state()
    worker_id = state.get("worker_id")

    saved_name = state.get("worker_name", "")
    if saved_name and saved_name != worker_name:
        print(f"[register] Name changed ({saved_name} -> {worker_name}), re-registering...")
        worker_id = None
    elif worker_id:
        # Verify still valid
        print(f"[register] Found saved worker ID: {worker_id[:8]}...")
        if heartbeat(server_url, worker_id):
            print(f"[register] Worker still active on server.")
        else:
            print(f"[register] Saved worker not found, re-registering...")
            worker_id = None

    if not worker_id:
        worker_id = register_worker(server_url, worker_name, {
            "tier": tier,
            "ram_gb": hw["ram_gb"],
            "cores": hw["cores"],
            "has_gpu": hw["has_gpu"],
            "gpu_type": hw["gpu_type"],
            "task_types": task_types,
        })
        save_state({"worker_id": worker_id, "worker_name": worker_name})

    # Start the loop
    try:
        run(server_url, worker_id, task_types)
    except KeyboardInterrupt:
        print("\n[worker] Shutting down. Thanks for contributing!")
        print(f"[worker] ID: {worker_id}")


if __name__ == "__main__":
    main()
