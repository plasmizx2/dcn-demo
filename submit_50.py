import random
import requests
import json

SERVER = "https://trula-functionless-bernardine.ngrok-free.dev"

# --- ML Experiment templates (the hero demo - bulk of jobs) ---
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

# --- Image Processing templates (real accessible test images) ---
image_jobs = [
    {
        "title": "Product Photo Batch - Electronics",
        "input_payload": {
            "image_urls": [
                "https://picsum.photos/id/0/800/600",
                "https://picsum.photos/id/1/800/600",
                "https://picsum.photos/id/2/800/600",
                "https://picsum.photos/id/3/800/600",
                "https://picsum.photos/id/4/800/600",
            ],
            "width": 1024,
            "quality": 85,
        },
    },
    {
        "title": "Marketing Assets - Resize Pipeline",
        "input_payload": {
            "image_urls": [
                "https://picsum.photos/id/10/800/600",
                "https://picsum.photos/id/11/800/600",
                "https://picsum.photos/id/12/800/600",
                "https://picsum.photos/id/13/800/600",
            ],
            "width": 640,
            "quality": 90,
        },
    },
    {
        "title": "Thumbnail Generation - Blog Images",
        "input_payload": {
            "image_urls": [
                "https://picsum.photos/id/20/800/600",
                "https://picsum.photos/id/21/800/600",
                "https://picsum.photos/id/22/800/600",
                "https://picsum.photos/id/23/800/600",
                "https://picsum.photos/id/24/800/600",
                "https://picsum.photos/id/25/800/600",
            ],
            "width": 300,
            "quality": 75,
        },
    },
]

# --- Web Scraping templates (real accessible public sites) ---
scraping_jobs = [
    {
        "title": "Tech News Aggregation",
        "input_payload": {
            "urls": [
                "https://news.ycombinator.com",
                "https://lobste.rs",
                "https://www.reddit.com/r/programming/.json",
            ]
        },
    },
    {
        "title": "Python Package Metadata Scrape",
        "input_payload": {
            "urls": [
                "https://pypi.org/project/requests/",
                "https://pypi.org/project/fastapi/",
                "https://pypi.org/project/numpy/",
                "https://pypi.org/project/scikit-learn/",
            ]
        },
    },
    {
        "title": "Wikipedia Reference Extraction",
        "input_payload": {
            "urls": [
                "https://en.wikipedia.org/wiki/Machine_learning",
                "https://en.wikipedia.org/wiki/Distributed_computing",
                "https://en.wikipedia.org/wiki/Neural_network",
            ]
        },
    },
]

# --- Sentiment Classification templates (real text, processable) ---
sentiment_jobs = [
    {
        "title": "Customer Review Sentiment - Q1 Batch",
        "input_payload": {
            "texts": [
                "Absolutely love this product, best purchase I've made all year!",
                "Shipping was slow but the quality exceeded my expectations.",
                "Terrible customer service. Waited 3 hours on hold and got nowhere.",
                "It's fine for the price. Nothing special but gets the job done.",
                "DO NOT BUY. Broke after two days. Complete waste of money.",
                "The new update is fantastic, really improved the user experience.",
                "Meh. I've seen better alternatives for half the price.",
                "Outstanding build quality and the battery lasts forever.",
            ]
        },
    },
    {
        "title": "Social Media Brand Mentions Analysis",
        "input_payload": {
            "texts": [
                "Just tried the new feature and it's a game changer!",
                "Why does the app keep crashing every time I open it?",
                "Switched from the competitor and couldn't be happier.",
                "The pricing is getting out of hand, considering alternatives.",
                "Their support team resolved my issue in under 10 minutes. Impressed.",
                "Another outage? This is getting ridiculous.",
                "Finally a company that listens to user feedback!",
                "The onboarding experience was smooth and intuitive.",
                "Lost all my data after the latest update. Furious.",
                "Decent product but the documentation is severely lacking.",
            ]
        },
    },
    {
        "title": "Employee Satisfaction Survey Analysis",
        "input_payload": {
            "texts": [
                "Great work-life balance and supportive management.",
                "The compensation doesn't match the workload at all.",
                "Love the remote work flexibility and team culture.",
                "Too many meetings, not enough time for actual work.",
                "The company genuinely cares about professional development.",
                "Communication between departments is practically nonexistent.",
            ]
        },
    },
    {
        "title": "App Store Review Classification",
        "input_payload": {
            "texts": [
                "Five stars! This app has completely replaced my old workflow.",
                "Keeps asking for permissions it doesn't need. Uninstalled.",
                "Solid app, just wish it had dark mode.",
                "Crashes on startup on my phone. Pixel 7, Android 14.",
                "The free tier is surprisingly generous. Will upgrade soon.",
                "Used to be great but the last few updates ruined it.",
            ]
        },
    },
]

# --- Audio Transcription templates ---
audio_jobs = [
    {
        "title": "Podcast Episode Transcription Batch",
        "input_payload": {
            "audio_urls": [
                "https://www.kozco.com/tech/LRMonoPhase4.wav",
                "https://www.kozco.com/tech/piano2-CoolEdit.mp3",
                "https://www.kozco.com/tech/organfinale.wav",
            ]
        },
    },
    {
        "title": "Meeting Recording Transcription",
        "input_payload": {
            "audio_urls": [
                "https://www.kozco.com/tech/LRMonoPhase4.wav",
                "https://www.kozco.com/tech/piano2-CoolEdit.mp3",
            ]
        },
    },
]

# --- Build the 50-job queue ---
jobs = []

# 25 ML experiments (the hero demo)
for i in range(25):
    t = dict(random.choice(ml_jobs))
    t["task_type"] = "ml_experiment"
    t["title"] = f"{t['title']} #{i+1}"
    jobs.append(t)

# 6 image processing
for i in range(6):
    t = dict(random.choice(image_jobs))
    t["task_type"] = "image_processing"
    t["input_payload"] = dict(t["input_payload"])
    t["title"] = f"{t['title']} #{i+1}"
    jobs.append(t)

# 6 web scraping
for i in range(6):
    t = dict(random.choice(scraping_jobs))
    t["task_type"] = "web_scraping"
    t["input_payload"] = dict(t["input_payload"])
    t["title"] = f"{t['title']} #{i+1}"
    jobs.append(t)

# 8 sentiment classification
for i in range(8):
    t = dict(random.choice(sentiment_jobs))
    t["task_type"] = "sentiment_classification"
    t["input_payload"] = dict(t["input_payload"])
    t["title"] = f"{t['title']} #{i+1}"
    jobs.append(t)

# 5 audio transcription
for i in range(5):
    t = dict(random.choice(audio_jobs))
    t["task_type"] = "audio_transcription"
    t["input_payload"] = dict(t["input_payload"])
    t["title"] = f"{t['title']} #{i+1}"
    jobs.append(t)

# Shuffle so it's a mixed queue
random.shuffle(jobs)

# Submit
print(f"Submitting {len(jobs)} jobs to {SERVER}...")
print(f"  25 ml_experiment | 6 image_processing | 6 web_scraping | 8 sentiment | 5 audio\n")

submitted = 0
for i, t in enumerate(jobs):
    t["priority"] = random.choices([1, 2, 3, 4], weights=[30, 35, 25, 10])[0]
    t["reward_amount"] = round(random.uniform(0.50, 4.00), 2)
    t["requires_validation"] = random.choice([True, False])

    try:
        resp = requests.post(f"{SERVER}/jobs", json=t, timeout=15)
        if resp.status_code == 200:
            submitted += 1
            print(f"[{i+1:2d}/50] OK  {t['task_type']:26s} | P{t['priority']} | {t['title']}")
        else:
            print(f"[{i+1:2d}/50] ERR {resp.status_code} | {t['title']}: {resp.text[:80]}")
    except Exception as e:
        print(f"[{i+1:2d}/50] ERR {t['title']}: {e}")
        break

print(f"\nDone! Submitted {submitted}/50 jobs.")
