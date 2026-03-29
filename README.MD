# DCN: Distributed Compute Network for Agentic AI Orchestration

DCN is a distributed task orchestration system that decomposes complex AI workloads into parallel subtasks, executes them across multiple worker nodes, and aggregates results into unified outputs. Users submit a high-level task and DCN handles decomposition, scheduling, execution, and aggregation automatically -- no workflow definitions, no DAGs, no infrastructure setup.

Built with FastAPI, PostgreSQL, and Google Gemini.

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

### `/` -- Job Submission UI

The public interface where users submit jobs and watch them execute in real time:
- Select from 10 task types with dynamic input fields (URL input for codebase review, dataset selector for ML experiments, textarea for text tasks)
- Each task type shows a "How it works" and "Why DCN at scale" explanation
- Live polling (1.5s) shows task status badges, progress bar, and worker activity
- On completion: **parallel vs sequential timing comparison** with animated bars showing speedup, worker count, and time saved
- Dual output rendering: HTML outputs get iframe preview + source tabs; markdown rendered via marked.js

### `/ops` -- Operator Dashboard

Real-time monitoring for operators:
- **Stats bar**: Total jobs, completed, queued tasks, running tasks, online/busy workers
- **Jobs table**: All jobs with status, type, and output indicators (click to inspect)
- **Worker Activity panel**: Each worker's status, current task assignment, and last heartbeat
- **Active Queue**: All queued/running tasks with worker assignments
- **Job Detail**: Task list with progress bar, status badges, and worker assignments
- **Timing comparison**: Completed jobs show parallel vs sequential execution bars with speedup stats
- **Event Feed**: Full lifecycle event log (job_created, task_started, task_submitted, etc.)

### `/results` -- Results Viewer

Browse and inspect completed job outputs with search, filtering, and tabbed rendering.

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

## All Supported Task Types (10)

| Task Type | Description | Planner Strategy | Aggregation |
|-----------|-------------|-----------------|-------------|
| `ml_experiment` | Distributed hyperparameter search | 8 parallel experiments with tiered difficulty | Custom ML ranking |
| `document_analysis` | AI analysis of text documents | Chunked text processing | Gemini synthesis |
| `codebase_review` | GitHub repo code review via API | File/module segmentation | Gemini synthesis |
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

## API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/` | Job submission UI |
| GET | `/ops` | Operator monitoring dashboard |
| GET | `/results` | Results viewer |
| GET | `/health` | Health check (verifies DB connection) |
| GET | `/jobs` | List all jobs |
| GET | `/jobs/{job_id}` | Get single job |
| POST | `/jobs` | Create job and plan subtasks (transactional) |
| GET | `/jobs/{job_id}/tasks` | Get job tasks |
| GET | `/jobs/{job_id}/timing` | Parallel vs sequential timing stats |
| GET | `/jobs/{job_id}/events` | Get event log |
| POST | `/tasks/claim` | Worker atomically claims next queued task |
| POST | `/tasks/{task_id}/complete` | Worker submits result, triggers aggregation |
| POST | `/tasks/{task_id}/fail` | Worker marks task failed |
| POST | `/workers/register` | Register new worker node |
| POST | `/workers/heartbeat` | Worker keepalive |
| GET | `/monitor/jobs` | All jobs for operator dashboard |
| GET | `/monitor/queue` | In-flight tasks (queued and running) |
| GET | `/monitor/stats` | Aggregate counts by status and worker health |
| GET | `/monitor/workers` | All workers with effective status |

## Project Structure

```
dcn-demo/
├── backend/
│   ├── main.py              # FastAPI app, lifespan, CORS, maintenance loop
│   ├── database.py          # Async connection pool (asyncpg)
│   ├── schemas.py           # Pydantic request/response models
│   ├── planner.py           # Task decomposition engine (314 lines)
│   ├── aggregator.py        # Result aggregation engine (393 lines)
│   ├── resource_guard.py    # CPU/RAM safety for ML workloads
│   ├── datasets.py          # Synthetic ML dataset generation (75K rows)
│   ├── requirements.txt
│   ├── ai/
│   │   └── gemini_client.py # Gemini 2.5 Flash integration
│   ├── apis/
│   │   ├── jobs.py          # Job CRUD, creation pipeline, timing endpoint
│   │   ├── workers.py       # Task claiming, completion, failure handling
│   │   └── monitor.py       # Operator dashboard endpoints
│   ├── handlers/
│   │   ├── document.py      # Document analysis handler
│   │   ├── codebase.py      # GitHub repo fetching and code review
│   │   ├── research.py      # Research pipeline handler
│   │   ├── website.py       # HTML/CSS generation handler
│   │   ├── data_processing.py # Data classification handler
│   │   └── ml_experiment.py # Distributed ML training (241 lines)
│   └── workers/
│       └── worker.py        # Worker loop with retry and backoff
├── frontend/
│   ├── public_page/
│   │   └── index.html       # Job submission SPA with timing visualization
│   ├── monitor/
│   │   └── index.html       # Operator dashboard with worker activity
│   └── results/
│       └── index.html       # Results browser with search and tabs
└── schema.sql               # Database DDL
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
- `http://localhost:8000/` -- Submit jobs
- `http://localhost:8000/ops` -- Monitor execution
- `http://localhost:8000/results` -- Browse outputs

## Task Status Flow

```
queued --> running --> submitted --> (aggregation check) --> job completed
               \--> failed
               \--> (stale >8min) --> requeued --> claimed by another worker
```
