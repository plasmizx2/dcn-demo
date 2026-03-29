import os
import random
import requests
import json

job_templates = [
    {
        "title": "Weather RI - Random Forest Tuning",
        "task_type": "ml_experiment",
        "input_payload": {"dataset_name": "weather_ri"}
    },
    {
        "title": "Customer Churn - Logistic Sweep",
        "task_type": "ml_experiment",
        "input_payload": {"dataset_name": "customer_churn"}
    },
    {
         "title": "High-Res Image Processing Pipeline",
         "task_type": "image_processing",
         "input_payload": {"image_urls": [f"http://example.com/img_{i}.jpg" for i in range(10)]}
    },
    {
         "title": "Competitor Price Indexing",
         "task_type": "web_scraping",
         "input_payload": {"urls": [f"http://example.com/item_{i}" for i in range(5)]}
    },
    {
         "title": "Support Call Log Transcription",
         "task_type": "audio_transcription",
         "input_payload": {"audio_urls": [f"http://example.com/call_{i}.mp3" for i in range(3)]}
    },
    {
         "title": "Social Media Mentions Sentiment",
         "task_type": "sentiment_classification",
         "input_payload": {"texts": [
             "This network is insanely fast!",
             "My connection dropped again.",
             "Is anyone else experiencing downtime?",
             "Great customer support, resolved my issue in 5 mins."
         ]}
    }
]

print("Submitting 50 diverse random jobs to DCN network...")
submitted = 0
for i in range(50):
    t = dict(random.choice(job_templates))
    t["title"] = f"{t['title']} - Run #{i+1}"
    t["priority"] = random.choices([1, 2, 3, 4], weights=[40, 30, 20, 10])[0]
    t["reward_amount"] = round(random.uniform(0.5, 3.5), 2)
    t["requires_validation"] = random.choice([True, False])
    
    try:
        resp = requests.post("http://localhost:8000/jobs", json=t)
        if resp.status_code == 200:
            submitted += 1
            print(f"[{i+1}/50] ✅ {t['title']} (Priority {t['priority']})")
        else:
            print(f"[{i+1}/50] ❌ Failed: {resp.status_code} - {resp.text}")
    except Exception as e:
         print(f"[{i+1}/50] ❌ API not responding: {e}")
         break

print(f"\nDone! Successfully queued {submitted} jobs.")
