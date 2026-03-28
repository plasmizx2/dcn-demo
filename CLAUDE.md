# DCN Demo — Claude Context

## What This Project Is

**DCN (Distributed Computation Network)** — a distributed task orchestration and AI processing system. Users submit jobs via a web dashboard, those jobs are split into subtasks, distributed to AI-powered worker nodes, and results are aggregated and displayed. Built as a hackathon/MVP demo.

---

## Stack

| Layer | Tech |
|-------|------|
| Backend | Python 3, FastAPI (async), asyncpg, PostgreSQL |
| Frontend | Vanilla HTML/JS (single-page, no framework) |
| AI | Google Gemini API (`google-genai`) |
| Env | `python-dotenv`, `.env` file (gitignored) |

---

## Project Structure

```
dcn-demo/
├── backend/
│   ├── main.py           # FastAPI app, lifespan DB pool, all routes
│   ├── database.py       # Async connection pool (asyncpg)
│   ├── schemas.py        # Pydantic request/response models
│   ├── requirements.txt  # fastapi, uvicorn, asyncpg, python-dotenv, requests, google-genai
│   ├── handlers/         # Per-task-type AI processing logic
│   └── workers/
│       └── worker.py     # Worker loop: claims tasks, runs handlers, posts results
└── frontend/
    └── public_page/
        └── index.html    # Full SPA (dark theme, inline CSS/JS)
```

---

## Environment Variables

```
DATABASE_URL=<postgres connection string>
GEMINI_API_KEY=<google gemini api key>
```

---

## API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/` | Serve frontend HTML |
| GET | `/health` | Health check |
| GET | `/jobs` | List all jobs |
| GET | `/jobs/{job_id}` | Get single job |
| POST | `/jobs` | Create job, plan subtasks |
| GET | `/jobs/{job_id}/tasks` | Get job's tasks |
| GET | `/jobs/{job_id}/events` | Get event log |
| POST | `/tasks/claim` | Worker atomically claims next queued task |
| POST | `/tasks/{task_id}/complete` | Worker submits result, triggers aggregation check |
| POST | `/tasks/{task_id}/fail` | Worker marks task failed |
| POST | `/workers/heartbeat` | Worker keepalive |
| GET | `/monitor/jobs` | Monitor: all jobs |
| GET | `/monitor/queue` | Monitor: queued/running tasks |
| GET | `/monitor/workers` | Monitor: all worker nodes |

---

## Database Schema

- **jobs** — id (UUID), title, description, task_type, input_payload, user_id, priority, reward_amount, requires_validation, status, final_output, created_at
- **job_tasks** — id, job_id, task_order, task_name, task_description, task_payload, status, worker_node_id, created_at
- **job_events** — id, job_id, event_type, message, created_at
- **task_results** — id, task_id, worker_node_id, result_text, result_payload, execution_time_seconds, status, created_at
- **worker_nodes** — id, node_name, status, last_heartbeat, created_at

---

## Task Types & Handlers

| Task Type | What It Does | Aggregation |
|-----------|-------------|-------------|
| `codebase_review` | Fetches GitHub repo files, AI code review | Concatenate |
| `document_analysis` | AI analysis of provided text | Gemini synthesis |
| `research_pipeline` | AI research on a topic | Gemini synthesis |
| `website_builder` | Generates HTML/CSS sections | Concatenate |
| `data_processing` | Classifies/analyzes data | Concatenate |

---

## Key Architectural Patterns

- **Atomic task claiming**: PostgreSQL `FOR UPDATE SKIP LOCKED` prevents duplicate claims in distributed workers
- **Event sourcing**: Every action logged (job_created, task_split, task_started, task_submitted, task_failed, job_completed)
- **Worker retry logic**: Exponential backoff (5s → 15s → 30s), double backoff on 429 rate limits
- **Two-tier aggregation**: Concatenation for code/data tasks, Gemini synthesis for analysis/research
- **Async throughout**: FastAPI async endpoints + asyncpg connection pool

---

## Task Status Flow

```
queued → running → submitted → (aggregation check) → job completed
                ↘ failed
```

---

## Frontend Behavior

- Polls `GET /jobs/{id}` + `GET /jobs/{id}/tasks` every 1500ms after job submit
- Progress bar = completed tasks / total tasks
- Shows live task list with status badges
- Displays final_output when job completes
- 5 task types, dynamic input field (URL for codebase_review, textarea for others)

---

## Known MVP Limitations / TODOs

- Task splitting is **static** (always 3 subtasks) — planner has TODOs for real splitting logic
- **No authentication** — open endpoints, demo only
- `requires_validation` field exists but not implemented
- No worker registration/deregistration UI
- Single Gemini API client, no global rate limiting layer
- No Docker/deployment config yet
