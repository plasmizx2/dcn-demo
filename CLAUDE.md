# DCN Demo — Claude Context

## What This Project Is

**DCN (Distributed Computation Network)** — a distributed task orchestration and AI processing system. Users submit jobs via a web dashboard, those jobs are split into subtasks dynamically by a smart planner, distributed to tiered AI-powered worker nodes, and results are aggregated and displayed. Built for a high-performance hackathon evaluation.

---

## Stack

| Layer | Tech |
|-------|------|
| Backend | Python 3, FastAPI (async), asyncpg, PostgreSQL |
| Frontend | Vanilla HTML/CSS/JS (multi-page, `Math.max` high-performance UI stats logic) |
| AI | Google Gemini API (`google-genai`), Open Source ML (scikit-learn) |
| Testing | `pytest` for integration, custom `smoke_test.py` |
| Env | `python-dotenv`, `.env` file |

---

## Project Structure

```
dcn-demo/
├── backend/
│   ├── main.py           # FastAPI app, lifespan DB pool, all routes
│   ├── database.py       # Async connection pool (asyncpg)
│   ├── schemas.py        # Pydantic request/response models
│   ├── planner.py        # Dynamic task decomposition logic (10 task types)
│   ├── aggregator.py     # Results aggregation, ML ranking, merging algorithms
│   ├── config.py         # Config constants, timeouts, job bounds
│   ├── utils.py          # Shared helpers, JSON parsing, prompt building
│   ├── auth.py           # Cookie session auth, RBAC (admin/customer)
│   ├── apis/             # Routers: jobs.py, workers.py, monitor.py
│   ├── handlers/         # Per-task AI and ML processing logic
│   └── workers/
│       └── worker.py     # Worker polling loop, tiered claiming, retry logic
├── frontend/             # Landing, login, ops monitor, results, and submit UI
└── tests/                # 54+ tests for planners, auth, schemas, and aggregators
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
| GET | `/` | Serve landing HTML |
| POST | `/auth/login` | Login and issue `dcn_session` cookie |
| GET | `/health` | Health check + DB connection test |
| GET | `/jobs` | List all jobs |
| POST | `/jobs` | Create job (Validates type, priority bounds) |
| GET | `/jobs/{id}/tasks` | Get tasks for job |
| DELETE| `/jobs/all` | Admin-only wipe |
| POST | `/tasks/claim` | Tiered worker atomically claims task |
| POST | `/tasks/{id}/complete` | Worker submits result, triggers validation flow |
| POST | `/tasks/{id}/validate` | Admin approves pending task |
| POST | `/tasks/{id}/fail` | Mark task failed |
| POST | `/workers/heartbeat` | Worker keepalive (defines active/offline) |
| GET | `/api/...` / `/monitor/...` | Expose stats and historical data |

---

## Database Schema

- **jobs** — id, title, task_type, user_id, priority, reward_amount, requires_validation, status, final_output, created_at
- **job_tasks** — id, job_id, task_order, task_name, task_payload, status, worker_node_id, created_at
- **job_events** — id, job_id, event_type, message, created_at
- **task_results** — id, task_id, worker_node_id, result_text, result_payload, status, created_at
- **worker_nodes** — id, node_name, status, last_heartbeat, created_at

---

## Task Types & Handlers (10 total)

| Task Type | Behavior | Aggregation Strategy |
|-----------|----------|----------------------|
| `document_analysis` | Splits by char length into chunks | Gemini Synthesis |
| `codebase_review` | Spawns architecture/logic/quality subtasks | Concatenation |
| `website_builder` | Detects/spawns specific layout sections | Concatenation |
| `research_pipeline` | 4-phase structured analysis pipeline | Gemini Synthesis |
| `data_processing` | Chunked processing of data rows | Concatenation |
| `ml_experiment` | Distributes hyperparameter search across workers | JSON metric extraction & ranking |
| `image_processing` | Distributed batching for images | Dist-Concatenate |
| `web_scraping` | Distributed url scraping | Dist-Concatenate |
| `audio_transcription` | Distributed speech-to-text | Dist-Concatenate |
| `sentiment_classification` | Batched sentiment scoring | Merge & Compute Totals |

---

## Key Architectural Patterns

- **Smart Planners**: Handlers no longer static. They dynamically split text by length, split arrays into chunks, and orchestrate ML pipelines.
- **Validation Workflow**: If `requires_validation=True`, worker completions sit at `pending_validation` until an admin explicitly calls POST `/tasks/{id}/validate` before aggregation triggers.
- **Tiered Cloud Edge Workers**: Workers detect core/RAM/GPU and self-identify Tier 1-4. Planners can enforce `min_tier` payloads.
- **Atomic task claiming**: PostgreSQL `FOR UPDATE SKIP LOCKED` prevents race conditions.
- **Event sourcing**: Full lifecycle trace from `job_created` -> `task_pending_validation` -> `task_validated` -> `job_completed`.

---

## Continuous Testing & Validation

- Code runs without magic numbers (`config.py`).
- 54-test Integration suite testing Planner Decomposition, Concatenators, Schemas, and Error Handling.
- Type hints on all FastAPI routes to ensure IDE compliance.
- All code uses standard library Python `logging` for tracing rather than bare `print()`.

---

## Next Steps / Backlog

- Switch in-memory User/Sessions array to DB-backed authentication.
- Implement rate limiting layer for Gemini tokens (currently client-only exponential backoff).
- Full scale stress-testing (1,000+ jobs concurrently).
