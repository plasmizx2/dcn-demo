import random
import requests
import json

SERVER = "https://trula-functionless-bernardine.ngrok-free.dev"

# --- ML Experiment templates ---
ml_jobs = [
    {"title": "Weather RI - Full Model Sweep", "input_payload": {"dataset_name": "weather_ri"}},
    {"title": "Weather RI - Tree Ensemble Focus", "input_payload": {"dataset_name": "weather_ri"}},
    {"title": "Weather RI - Linear Baselines", "input_payload": {"dataset_name": "weather_ri"}},
    {"title": "Weather RI - Gradient Boost Tuning", "input_payload": {"dataset_name": "weather_ri"}},
    {"title": "Weather RI - Feature Subset Experiment", "input_payload": {"dataset_name": "weather_ri"}},
    {"title": "Customer Churn - Classification Sweep", "input_payload": {"dataset_name": "customer_churn"}},
    {"title": "Customer Churn - Ensemble Models", "input_payload": {"dataset_name": "customer_churn"}},
    {"title": "Customer Churn - Logistic Baselines", "input_payload": {"dataset_name": "customer_churn"}},
    {"title": "Customer Churn - Boosting Comparison", "input_payload": {"dataset_name": "customer_churn"}},
    {"title": "Customer Churn - Tree Depth Analysis", "input_payload": {"dataset_name": "customer_churn"}},
]

# --- Build the 50-job queue ---
jobs = []

for i in range(50):
    t = dict(random.choice(ml_jobs))
    t["task_type"] = "ml_experiment"
    t["title"] = f"{t['title']} #{i+1}"
    jobs.append(t)

# Shuffle so it's a mixed queue
random.shuffle(jobs)

# Submit
print(f"Submitting {len(jobs)} ml_experiment jobs to {SERVER}...\n")

submitted = 0
for i, t in enumerate(jobs):
    t["priority"] = random.choices([1, 2, 3, 4], weights=[30, 35, 25, 10])[0]
    t["reward_amount"] = round(random.uniform(0.50, 4.00), 2)
    t["requires_validation"] = random.choice([True, False])

    try:
        resp = requests.post(f"{SERVER}/jobs", json=t, timeout=15)
        if resp.status_code == 200:
            submitted += 1
            print(f"[{i+1:2d}/50] OK  ml_experiment | P{t['priority']} | {t['title']}")
        else:
            print(f"[{i+1:2d}/50] ERR {resp.status_code} | {t['title']}: {resp.text[:80]}")
    except Exception as e:
        print(f"[{i+1:2d}/50] ERR {t['title']}: {e}")
        break

print(f"\nDone! Submitted {submitted}/50 jobs.")
