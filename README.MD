# DCN: Distributed Compute Network

## Overview
DCN is a distributed AI orchestration system that decomposes tasks into parallel subtasks, executes them across multiple workers, and aggregates results into a final output.

It transforms sequential AI workflows into distributed execution pipelines.

---

## Architecture

1. Job Submission  
Users submit a job with a task type and input.

2. Planner  
The planner decomposes the job into multiple subtasks.

3. Workers  
Workers poll, claim, execute, and submit results.

4. Aggregation  
Results are combined into a final output.

5. Monitoring  
Dashboard shows jobs, tasks, workers, and events.

---

## Supported Task Types

- document_analysis  
- codebase_review  
- website_builder  
- research_pipeline  
- data_processing  
- ml_experiment  
- image_processing  
- web_scraping  
- audio_transcription  
- sentiment_classification  

---

## Distributed ML Experiment System

DCN supports distributed ML experimentation:
- multiple models trained in parallel
- cross-validation and evaluation
- model comparison and ranking
- best model selection with reusable config

---

## Key Features

- distributed task execution  
- automatic task decomposition  
- worker-based execution system  
- priority and tier-based scheduling  
- retry logic and failure handling  
- aggregation strategies per task type  
- event logging and monitoring dashboard  

---

## Tech Stack

- FastAPI (backend)
- Supabase / PostgreSQL (database)
- Gemini API (AI processing)
- JavaScript frontend

---

## Execution Flow

1. User submits job  
2. Planner splits job into tasks  
3. Workers claim tasks  
4. Tasks executed in parallel  
5. Results aggregated  
6. Final output returned  

---

## How to Run

```bash
pip install -r requirements.txt
uvicorn main:app --reload