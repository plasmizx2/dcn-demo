# DCN: Distributed Compute Network for Agentic AI Orchestration

[![GitHub](https://img.shields.io/badge/GitHub-plasmizx2%2Fdcn--demo-181717?logo=github)](https://github.com/plasmizx2/dcn-demo)
[![Live Demo](https://img.shields.io/badge/Live_Demo-dcn--demo.onrender.com-7c3aed)](https://dcn-demo.onrender.com)
[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-async-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)

DCN is a distributed task orchestration system that decomposes complex AI workloads into parallel subtasks, executes them across multiple worker nodes, and aggregates results into unified outputs. Users submit a high-level task and DCN handles decomposition, scheduling, execution, and aggregation automatically — no workflow definitions, no DAGs, no infrastructure setup.

Built with FastAPI, PostgreSQL, and Google Gemini.

> **Live demo**: [dcn-demo.onrender.com](https://dcn-demo.onrender.com)  
> **Source**: [github.com/plasmizx2/dcn-demo](https://github.com/plasmizx2/dcn-demo)

---

## ⚡ Start Here — Demo Path

Fastest way to see DCN in action:

1. **Open** [dcn-demo.onrender.com](https://dcn-demo.onrender.com) (first load may take ~30s on free tier)
2. **Sign in** as `admin` / `admin123`
3. **Submit** an `ml_experiment` job → select the **weather** dataset → hit Submit
4. **Watch** `/ops` — see 8 parallel experiments fan out to worker nodes in real time
5. **Compare** the parallel vs sequential timing bars when the job completes (typically 3-5× speedup)
6. **Inspect** `/results` — view the ranked model comparison table with the winning model highlighted

**Best supporting demos**: `document_analysis` (paste any long text) and `codebase_review` (paste a GitHub URL) — these show the AI synthesis aggregation path.

---

## Deployment

| Environment | URL | Notes |
|---|---|---|
| **Production** | [dcn-demo.onrender.com](https://dcn-demo.onrender.com) | Render Web Service (backend) + Supabase (PostgreSQL) |
| **Workers** | Render Background Workers | Auto-register, heartbeat every 30s |
| **Local** | `http://localhost:8000` | See [Setup](#setup) below |

## Screenshots

<!-- Add your screenshots here. Take them from the live demo at dcn-demo.onrender.com -->
<!-- Recommended: landing page, submit page, /ops dashboard mid-job, results with ML ranking -->

| Landing Page | Operator Dashboard |
|:---:|:---:|
| ![Landing](docs/screenshots/landing.png) | ![Dashboard](docs/screenshots/dashboard.png) |

| ML Experiment Results | Job Submission |
|:---:|:---:|
| ![Results](docs/screenshots/results.png) | ![Submit](docs/screenshots/submit.png) |

## Architecture

```
User submits job via web UI (/)
             |
          Planner
          (decomposes job into N subtasks based on task type)
             |
    +--------+--------+--------+
    |        |        |        |
 Worker 1  Worker 2  Worker 3  Worker N
 (claims)  (claims)  (claims)  (claims)
    |        |        |        |
 Result    Result   Result   Result
    |        |        |        |
    +--------+--------+--------+
             |
         Aggregator
         (combines results using task-type-specific strategy)
             |
         Final Output
         (displayed in UI with timing comparison)
```

### How It Works

1. **User submits a job** at `/` with a task type and input (GitHub URL, document text, ML dataset, etc.)
2. **Planner decomposes** the job into parallel subtasks (3-8 depending on type)
3. **Workers independently claim** tasks using atomic database locks (`FOR UPDATE SKIP LOCKED`)
4. **Each worker executes** its task (AI inference, ML training, data processing) and reports results
5. **Aggregator combines** all results into a final output using the appropriate strategy (ML ranking, AI synthesis, distributed merge)
6. **UI displays** the final output with a parallel vs sequential timing comparison

### Core Components

- **Job API** -- FastAPI async endpoints for job submission, task management, worker coordination, and monitoring
- **Planner** -- Decomposes jobs into parallel subtasks with task-type-specific splitting logic (input-aware batch splitting, parametric ML experiment generation, semantic segmentation)
- **Worker Pool** -- Independent workers poll for tasks, claim via atomic database locks, execute with retry logic and exponential backoff, and report results
- **Aggregator** -- Four aggregation strategies: ML experiment ranking, distributed result merging with deduplication, Gemini AI synthesis, and ordered concatenation
- **Monitoring Dashboard** -- Real-time operator visibility into jobs, tasks, worker health, and event timelines at `/ops`

## Web Interfaces

### `/` — Landing Page

Animated marketing landing page with:
- Live platform stats (animated counters), floating gradient orbs, and grid background
- "How It Works" 4-step flow, capability cards (10 task types), architecture diagram
- Pipeline visualization showing job → planner → workers → aggregator flow
- Role-aware navigation (shows Dashboard/Results links for admins)

### `/login` — Authentication

Minimal frosted-glass login form. Demo credentials:
- **Admin**: `admin` / `admin123` → full access (dashboard, results, worker logs)
- **Customer**: `customer` / `customer123` → submit page + my jobs only

### `/submit` — Job Submission UI

The primary interface where users submit jobs and watch them execute in real time:
- Select from 10 task types with dynamic input fields (URL input for codebase review, dataset selector for ML experiments, textarea for text tasks)
- Each task type shows a "How it works" and "Why DCN at scale" explanation
- Live polling (1.5s) shows task status badges, progress bar, and worker activity
- On completion: **parallel vs sequential timing comparison** with animated bars showing speedup, worker count, and time saved
- Dual output rendering: HTML outputs get iframe preview + source tabs; markdown rendered via marked.js
- Role-aware sidebar navigation (admin sees all pages, customer sees submit + my jobs)

### `/my-jobs` — My Jobs

Customer-facing job tracker:
- Lists all submitted jobs with status badges, progress bars, and type tags
- Click to expand: task list with individual statuses, and final output preview (markdown rendered)
- Auto-refreshes every 5 seconds
- Available to all authenticated users

### `/ops` — Operator Dashboard (admin only)

Real-time monitoring for operators:
- **Stats bar**: Total jobs, completed, queued tasks, running tasks, online/busy workers
- **Jobs table**: All jobs with status, type, and output indicators (click to inspect)
- **Worker Activity panel**: Each worker's status, current task assignment, and last heartbeat
- **Active Queue**: All queued/running tasks with worker assignments
- **Job Detail**: Task list with progress bar, status badges, and worker assignments
- **Timing comparison**: Completed jobs show parallel vs sequential execution bars with speedup stats
- **Event Feed**: Full lifecycle event log (job_created, task_started, task_submitted, etc.)

### `/results` — Results Viewer (admin only)

Browse and inspect completed job outputs with search, filtering, and tabbed rendering (Rendered, Raw, Tasks, Preview).

### `/worker-logs` — Worker Logs (admin only)

Worker node monitoring and diagnostics:
- Worker cards showing status (online/busy/offline), heartbeat timing
- Click to view full task history: task name, parent job, status, execution time
- Aggregate stats: total tasks processed, completion/failure rate, average execution time

### 404 — Custom Error Page

Branded error page with animated background glows and navigation links.

## Hero Demo: ML Experiment Pipeline

The ML experiment system is the core demo -- it shows distributed compute at its most impactful.

### What Happens

1. User selects `ml_experiment` and picks a dataset (weather or churn)
2. Planner generates **8 parallel experiments** with different models and hyperparameters:
   - LinearRegression (baseline, tier 2)
   - Ridge regression (alpha=1.0, tier 2)
   - DecisionTree (max_depth=15, tier 2)
   - RandomForest (200 trees, depth=10, tier 3)
   - RandomForest (500 trees, depth=20, tier 4)
   - GradientBoosting (200 trees, depth=5, lr=0.1, tier 3)
   - RandomForest with reduced features (tier 2)
   - GradientBoosting tuned (500 trees, depth=8, lr=0.05, tier 4)
3. Workers claim experiments based on their tier capability
4. Each worker independently: loads 75K-row dataset, applies resource guards, runs 5-fold cross-validation, trains model, computes test metrics, returns structured JSON + markdown
5. Aggregator collects all 8 results, ranks models by primary metric (R2 or F1), produces comparison table with best model highlighted

### Datasets

- **weather_ri** -- 75K rows, 16 features, regression target: temperature. Nonlinear model with seasonal, time-of-day, wind-direction, coastal, and elevation effects.
- **customer_churn** -- 75K rows, 12 features, classification target: churn. Logistic model with tenure, contract, product, and support interaction effects.

### Models (14 types)

Regression: LinearRegression, Ridge, DecisionTreeRegressor, RandomForestRegressor, GradientBoostingRegressor
Classification: LogisticRegression, LogisticRegression L1, DecisionTreeClassifier, RandomForestClassifier, GradientBoostingClassifier

### Metrics

- Regression: R2, MSE, MAE, CV R2 mean/std
- Classification: F1, accuracy, precision, recall, CV F1 mean/std

### Output

Ranked model comparison table, best model detail, execution summary, and reusable JSON config for the winning model.

### Resource Guards

- `safe_n_jobs()` reserves 2 CPU cores for the OS during parallel training
- `safe_dataset_size()` caps rows based on available RAM (25K rows/GB, floor 5K) to prevent OOM

## Parallel vs Sequential Execution

Every completed job shows a timing comparison that demonstrates the core value of distributed execution:

- **Sequential time** = sum of all individual task execution times (what it would take on one machine)
- **Parallel time** = wall-clock time from first task claimed to last task completed (actual distributed run)
- **Speedup** = sequential / parallel

The timing is computed from real execution data stored in `task_results.execution_time_seconds` and `job_tasks.started_at` / `completed_at` timestamps -- not simulated.

Both the public UI (`/`) and operator dashboard (`/ops`) display this comparison with animated bar charts showing the speedup, number of workers used, and total time saved.

## Supported Task Types

The **hero demo** is `ml_experiment` — it shows real distributed compute with measurable parallel speedup, structured model comparison, and resource-aware execution.

The **strongest supporting flows** are `document_analysis` and `codebase_review` — they demonstrate the AI synthesis aggregation path (Gemini combines parallel subtask results into a coherent report).

All 10 types are fully implemented:

| Task Type | Description | Planner Strategy | Aggregation |
|-----------|-------------|-----------------|-------------|
| **`ml_experiment`** ⭐ | Distributed hyperparameter search | 8 parallel experiments with tiered difficulty | Custom ML ranking |
| **`document_analysis`** | AI analysis of text documents | Chunked text processing | Gemini synthesis |
| **`codebase_review`** | GitHub repo code review via API | File/module segmentation | Gemini synthesis |
| `website_builder` | HTML/CSS section generation | Section-based generation | Concatenation |
| `research_pipeline` | Multi-phase research on a topic | Phased breakdown | Gemini synthesis |
| `data_processing` | Data classification and analysis | Batch-based execution | Concatenation |
| `image_processing` | Batch image analysis | URL list splitting across workers | Distributed merge |
| `web_scraping` | Parallel URL scraping | URL list splitting across workers | Distributed merge |
| `audio_transcription` | Parallel audio file transcription | URL list splitting across workers | Distributed merge |
| `sentiment_classification` | Text sentiment analysis at scale | Text list splitting across workers | Sentiment-aware merge |

## Technical Design

### Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3, FastAPI (async), asyncpg |
| Database | PostgreSQL (Supabase) |
| AI | Google Gemini 2.5 Flash (`google-genai`) |
| ML | scikit-learn, NumPy |
| Frontend | Vanilla HTML/JS (single-page app) |

### Database Schema

5 tables with full relational integrity:

- **jobs** -- id (UUID), title, description, task_type, input_payload (JSONB), status, priority, reward_amount, final_output, created_at, updated_at
- **job_tasks** -- id, job_id (FK CASCADE), task_order, task_name, task_payload (JSONB), status, worker_node_id, started_at, completed_at
- **task_results** -- id, task_id (FK CASCADE), worker_node_id, result_text, result_payload (JSONB), execution_time_seconds
- **worker_nodes** -- id, node_name, status, cpu_cores, ram_gb, gpu_name, last_heartbeat
- **job_events** -- id, job_id, event_type, message, metadata (JSONB), created_at

### Task Claim Protocol

Workers claim tasks using PostgreSQL pessimistic locking:

```sql
UPDATE job_tasks SET status='running', worker_node_id=$1, started_at=NOW()
WHERE id = (
  SELECT jt.id FROM job_tasks jt
  JOIN jobs j ON j.id = jt.job_id
  WHERE jt.status = 'queued'
    AND j.task_type = ANY($2)
    AND COALESCE((jt.task_payload->>'min_tier')::int, 1) <= $3
  ORDER BY j.priority DESC,
           COALESCE((jt.task_payload->>'min_tier')::int, 1) DESC,
           jt.created_at
  LIMIT 1
  FOR UPDATE OF jt SKIP LOCKED
) RETURNING *
```

- `FOR UPDATE SKIP LOCKED` prevents race conditions across concurrent workers
- Three-level ordering: job priority DESC, task tier DESC (hard tasks first), FIFO within tier
- Workers pass their tier level; system only assigns tasks they can handle

### Worker Resilience

- **Exponential backoff**: 5s, 15s, 30s retry waits
- **Rate-limit detection**: Doubles wait on 429/rate/quota errors
- **4 total attempts** before marking task failed
- **Heartbeat-based liveness**: 30-second heartbeat window; workers marked offline if stale

### Background Maintenance

A background loop runs every 60 seconds:
- **Stale task reaper**: Tasks running >8 minutes are requeued (status reset, worker cleared, event logged)
- **Dead worker pruner**: Workers with no heartbeat for >1 hour are removed

### Aggregation Strategies

| Strategy | Used For | How It Works |
|----------|---------|-------------|
| **ML Ranking** | ml_experiment | Extracts JSON metrics from each experiment, ranks by primary metric (R2 or F1), produces comparison table and best model config |
| **Distributed Merge** | image, scraping, audio, sentiment | Regex-based header deduplication, item counting, sentiment-specific count aggregation across workers |
| **Gemini Synthesis** | document, research, codebase | Sends all subtask results to Gemini for coherent report generation |
| **Concatenation** | website, data | Section-ordered concatenation with headers |
| **Fallback chain** | All types | Synthesis attempt, fall back to concatenation on failure |

### Event Sourcing

Every state transition is logged to `job_events`:
- `job_created`, `task_split`, `task_started`, `task_submitted`, `task_failed`, `task_requeued`, `job_completed`, `job_failed`
- Each event includes metadata (JSONB) for debugging and audit

## Authentication

Cookie-based session auth with role-based access control:

| Role | Access |
|------|--------|
| **admin** | All pages: `/submit`, `/ops`, `/results`, `/worker-logs`, `/my-jobs` |
| **customer** | Public pages: `/submit`, `/my-jobs` |
| **anonymous** | Landing (`/`), login, health check |

- Sessions stored in-memory (swap to Redis/DB for production)
- Middleware auto-redirects unauthenticated users to `/login` for protected pages
- Admin API routes (`/monitor/*`) return 401 JSON for non-admin requests

## API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| **Pages** | | |
| GET | `/` | Landing page |
| GET | `/login` | Login page |
| GET | `/submit` | Job submission UI |
| GET | `/my-jobs` | Customer job tracker |
| GET | `/ops` | Operator dashboard (admin) |
| GET | `/results` | Results viewer (admin) |
| GET | `/worker-logs` | Worker logs (admin) |
| **Auth** | | |
| POST | `/auth/login` | Authenticate and create session |
| GET | `/auth/me` | Get current user info |
| GET/POST | `/auth/logout` | Destroy session and redirect |
| **Jobs** | | |
| GET | `/jobs` | List all jobs |
| GET | `/jobs/{job_id}` | Get single job |
| POST | `/jobs` | Create job and plan subtasks (transactional) |
| DELETE | `/jobs/all` | Clear all jobs (demo reset) |
| GET | `/jobs/{job_id}/tasks` | Get job tasks |
| GET | `/jobs/{job_id}/timing` | Parallel vs sequential timing stats |
| GET | `/jobs/{job_id}/events` | Get event log |
| **Workers** | | |
| POST | `/tasks/claim` | Worker atomically claims next queued task |
| POST | `/tasks/{task_id}/complete` | Worker submits result, triggers aggregation |
| POST | `/tasks/{task_id}/fail` | Worker marks task failed |
| POST | `/workers/register` | Register new worker node |
| POST | `/workers/heartbeat` | Worker keepalive |
| **Monitoring** | | |
| GET | `/monitor/jobs` | All jobs for operator dashboard |
| GET | `/monitor/queue` | In-flight tasks (queued and running) |
| GET | `/monitor/stats` | Aggregate counts by status and worker health |
| GET | `/monitor/workers` | All workers with effective status |
| GET | `/monitor/worker-history/{id}` | Task history for a specific worker |
| **Other** | | |
| GET | `/health` | Health check (verifies DB connection) |
| GET | `/stats` | Platform stats for landing page |

## Project Structure

```
dcn-demo/
├── backend/
│   ├── main.py              # FastAPI app, routes, auth middleware, maintenance loop
│   ├── auth.py              # Cookie-based auth, session management, role config
│   ├── users.json           # Demo user credentials
│   ├── database.py          # Async connection pool (asyncpg)
│   ├── schemas.py           # Pydantic request/response models
│   ├── planner.py           # Task decomposition engine
│   ├── aggregator.py        # Result aggregation engine
│   ├── resource_guard.py    # CPU/RAM safety for ML workloads
│   ├── datasets.py          # Synthetic ML dataset generation (75K rows)
│   ├── requirements.txt
│   ├── ai/
│   │   └── gemini_client.py # Gemini 2.5 Flash integration
│   ├── apis/
│   │   ├── jobs.py          # Job CRUD, creation pipeline, timing endpoint
│   │   ├── workers.py       # Task claiming, completion, failure handling
│   │   └── monitor.py       # Dashboard + worker history endpoints
│   ├── handlers/
│   │   ├── document.py      # Document analysis handler
│   │   ├── codebase.py      # GitHub repo fetching and code review
│   │   ├── research.py      # Research pipeline handler
│   │   ├── website.py       # HTML/CSS generation handler
│   │   ├── data_processing.py # Data classification handler
│   │   └── ml_experiment.py # Distributed ML training
│   └── workers/
│       └── worker.py        # Worker loop with retry and backoff
├── dcn-worker/
│   ├── app.py               # Standalone worker application
│   ├── hardware.py          # Hardware detection and tier assignment
│   └── run.py               # Worker runner script
├── frontend/
│   ├── landing/
│   │   └── index.html       # Marketing landing page with live stats
│   ├── login/
│   │   └── index.html       # Authentication page
│   ├── public_page/
│   │   └── index.html       # Job submission SPA with timing visualization
│   ├── my-jobs/
│   │   └── index.html       # Customer job tracker with expandable cards
│   ├── monitor/
│   │   └── index.html       # Operator dashboard with worker activity
│   ├── results/
│   │   └── index.html       # Results browser with search and tabs
│   ├── worker-logs/
│   │   └── index.html       # Worker diagnostics and task history
│   └── error/
│       └── 404.html         # Branded 404 page
├── schema.sql               # Database DDL
├── submit_50.py             # Batch job submission script (load testing)
├── tests/
│   └── smoke_test.py        # API and page route smoke tests
└── README.MD
```

## Setup

### Requirements

- Python 3.12+
- PostgreSQL database (Supabase)
- Google Gemini API key

### Environment Variables

```
DATABASE_URL=<postgres connection string>
GEMINI_API_KEY=<google gemini api key>
```

### Run

```bash
cd backend
pip install -r requirements.txt

# Start the API server
uvicorn main:app --host 0.0.0.0 --port 8000

# In separate terminals, start 1+ workers:
python -m workers.worker
```

Then open:
- `http://localhost:8000/` — Landing page
- `http://localhost:8000/login` — Sign in (admin/admin123 or customer/customer123)
- `http://localhost:8000/submit` — Submit jobs
- `http://localhost:8000/my-jobs` — Track your jobs
- `http://localhost:8000/ops` — Monitor execution (admin)
- `http://localhost:8000/results` — Browse outputs (admin)
- `http://localhost:8000/worker-logs` — Worker diagnostics (admin)

## Testing

Smoke tests verify that core endpoints, auth, page routes, and error handling are operational:

```bash
# Against local server
python tests/smoke_test.py

# Against production
python tests/smoke_test.py https://dcn-demo.onrender.com
```

Expected output:
```
🔍 DCN Smoke Tests — https://dcn-demo.onrender.com

Health & Core API:
  ✓ Health check — 200
  ✓ Stats endpoint — 200
  ✓ List jobs — 200

Authentication:
  ✓ Login page — 200
  ✓ Auth me (unauthenticated) — 401
  ✓ Login with bad creds — 401
  ...

Results: 12/12 passed — all clear ✓
```

### Manual Verification Checklist

- [ ] Landing page loads with animated stats and hero section
- [ ] Login works with admin/admin123 and customer/customer123
- [ ] Admin sidebar shows all 6 navigation links
- [ ] Customer sidebar shows only Submit + My Jobs
- [ ] `/ops` dashboard displays stats, job table, worker activity
- [ ] Submit `ml_experiment` → 8 tasks created and distributed
- [ ] Timing comparison appears on job completion
- [ ] Worker logs show task history per node
- [ ] Sign out works and redirects to login
- [ ] Unknown routes show branded 404 page

## Task Status Flow

```
queued --> running --> submitted --> (aggregation check) --> job completed
               \--> failed
               \--> (stale >8min) --> requeued --> claimed by another worker
```

## License

MIT
