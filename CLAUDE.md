# DCN — Distributed Computation Network

## What this project is

A hackathon MVP for a distributed job orchestration system. Users submit jobs, the system splits them into subtasks, AI workers process each task using Gemini, and results are aggregated into a final output.

## Tech stack

- **Backend:** FastAPI (Python, async)
- **Database:** PostgreSQL via Supabase (asyncpg driver)
- **AI:** Google Gemini 2.5 Flash via `google-genai`
- **Frontend:** Plain HTML/CSS/JS served through FastAPI
- **No auth, no WebSockets, no build tools**

## Architecture flow

```
User submits job → POST /jobs
  → planner.py splits into 3 subtasks (job_tasks table)
  → workers claim tasks via POST /tasks/claim (atomic, FOR UPDATE SKIP LOCKED)
  → workers process with Gemini AI (handlers/)
  → workers submit results via POST /tasks/{id}/complete
  → last task triggers aggregation (aggregator.py)
  → final_output saved to jobs table, status → completed
  → frontend polls and displays result
```

## Database tables (Supabase PostgreSQL)

- `jobs` — id, title, description, task_type, input_payload, status, final_output, user_id, priority, reward_amount, requires_validation
- `job_tasks` — id, job_id, task_order, task_name, task_description, task_payload, status, worker_node_id
- `job_events` — job_id, event_type, message, created_at
- `task_results` — task_id, worker_node_id, result_text, result_payload, execution_time_seconds, status
- `worker_nodes` — id, node_name, status, last_heartbeat

## Task types supported

- `codebase_review` — takes `github_url` in input_payload, fetches repo from GitHub API
- `document_analysis` — takes `text` in input_payload
- `research_pipeline` — takes `text` in input_payload
- `website_builder` — takes `text` in input_payload
- `data_processing` — takes `text` in input_payload

## Aggregation strategy (Step 9)

- **Concatenation** for: codebase_review, website_builder, data_processing (preserves all detail)
- **Gemini synthesis** for: document_analysis, research_pipeline (merges into coherent report)
- If Gemini synthesis fails, falls back to concatenation
- Triggers synchronously when the last task completes

## Error handling

- Worker retries up to 3 times with backoff: 5s → 15s → 30s
- Rate limit detection (429) doubles the wait time
- Aggregator falls back to concatenation if Gemini fails

## Key files

```
backend/
  main.py              — FastAPI app, serves frontend at /
  database.py          — asyncpg connection pool
  schemas.py           — Pydantic models (JobCreate, TaskClaim, TaskComplete, WorkerHeartbeat)
  planner.py           — splits jobs into subtasks by task_type
  aggregator.py        — combines task results into final job output
  apis/
    jobs.py            — POST /jobs, GET /jobs, GET /jobs/{id}, GET /jobs/{id}/tasks, GET /jobs/{id}/events
    workers.py         — POST /tasks/claim, POST /tasks/{id}/complete, POST /tasks/{id}/fail, POST /workers/heartbeat
    monitor.py         — GET /monitor/jobs, /monitor/queue, /monitor/workers
  handlers/
    codebase.py        — fetches GitHub repo, sends files to Gemini for review
    document.py        — document analysis handler
    research.py        — research pipeline handler
    website.py         — website builder handler
    data_processing.py — data processing handler
  ai/
    gemini_client.py   — Gemini API wrapper (generate_text function)
  workers/
    worker.py          — standalone worker process (run with: python workers/worker.py <worker_node_id>)
frontend/
  public_page/
    index.html         — demo UI (dark theme, job submission, status polling, output display)
```

## Environment variables (.env in backend/)

```
DATABASE_URL=postgresql://...   # Supabase PostgreSQL connection string
GEMINI_API_KEY=AIzaSy...        # Google Gemini API key
```

## How to run

1. `cd backend && pip install -r requirements.txt`
2. Create `.env` with DATABASE_URL and GEMINI_API_KEY
3. `uvicorn main:app --reload` (or `--host 0.0.0.0` for network access)
4. Open http://localhost:8000
5. In a separate terminal: `python workers/worker.py <worker_node_id>`

## Completed steps

- Step 5: Database schema (Supabase)
- Step 6: FastAPI backend with job/task/worker APIs
- Step 7: Worker system with task claiming
- Step 8: Gemini AI integration in handlers
- Step 9: Aggregation + final job output
- Step 10: Public demo frontend (in progress)

## Rules for working on this project

- Do NOT refactor existing working code unless absolutely necessary
- Do NOT add authentication yet
- Do NOT add WebSockets — use polling
- Do NOT add complex frameworks or build tools
- Do NOT add new database tables unless required
- Keep everything hackathon-simple
- The repo is public at https://github.com/plasmizx2/dcn-demo
