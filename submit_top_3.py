import requests
import json

SERVER = "https://dcn-demo.onrender.com"

jobs = [
    {
        "title": "DCN System Security & Logic Audit",
        "task_type": "codebase_review",
        "priority": 4,
        "reward_amount": 5.00,
        "input_payload": {
            "github_url": "https://github.com/plasmizx2/dcn-demo"
        }
    },
    {
        "title": "Weather Prediction - Distributed Hyperparameter Sweep",
        "task_type": "ml_experiment",
        "priority": 3,
        "reward_amount": 3.50,
        "input_payload": {
            "dataset_name": "weather_ri"
        }
    },
    {
        "title": "Enterprise Dashboard Architecture Mockup",
        "task_type": "website_builder",
        "priority": 2,
        "reward_amount": 2.75,
        "input_payload": {
            "prompt": "A sleek, high-contrast dashboard for a distributed compute network including charts, worker nodes, and task logs."
        }
    }
]

print(f"Submitting top 3 important jobs to {SERVER}...")

for i, job in enumerate(jobs):
    try:
        resp = requests.post(f"{SERVER}/jobs", json=job, timeout=15)
        if resp.status_code == 200:
            print(f"[{i+1}/3] OK  {job['task_type']:20s} | {job['title']}")
        else:
            print(f"[{i+1}/3] ERR {resp.status_code} | {job['title']}: {resp.text}")
    except Exception as e:
        print(f"[{i+1}/3] ERR {job['title']}: {e}")

print("\nSubmission complete.")
