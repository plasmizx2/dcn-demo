# DCN: Distributed Compute Network for Agentic AI Orchestration

A distributed task orchestration system that decomposes complex AI workloads into parallel subtasks, executes them across multiple worker nodes, and aggregates results into unified outputs. Built with FastAPI, PostgreSQL, and Google Gemini.

## Architecture

```
User submits job
       |
    Planner
    (splits job into subtasks based on task type)
       |
  +---------+---------+
  |         |         |
Worker 1  Worker 2  Worker N
(claims)  (claims)  (claims)
  |         |         |
  Results   Results   Results
  |         |         |
  +---------+---------+
       |
   Aggregator
   (combines results by task type)
       |
   Final Output
```

### Core Components

- **Job API** -- FastAPI async endpoints for job submission, task management, worker coordination, and monitoring
- **Planner** -- Decomposes jobs into parallel subtasks with task-type-specific splitting logic (chunking, segmentation, batching, phased breakdown)
- **Worker Pool** -- Independent workers poll for tasks, claim via atomic database locks, execute with retry logic, and report results
- **Aggregator** -- Three aggregation strategies: ML experiment ranking, distributed result merging with deduplication, and Gemini AI synthesis
- **Monitoring Dashboard** -- Real-time operator visibility into jobs, tasks, worker health, and event timelines

## Supported Task Types (10)

| Task Type | Description | Planner Strategy | Aggregation |
|-----------|-------------|-----------------|-------------|
| `document_analysis` | AI analysis of text documents | Chunked text processing | Gemini synthesis |
| `codebase_review` | GitHub repo code review via API | File/module segmentation | Gemini synthesis |
| `website_builder` | HTML/CSS section generation | Section-based generation | Concatenation |
| `research_pipeline` | Multi-phase research on a topic | Phased breakdown | Gemini synthesis |
| `data_processing` | Data classification and analysis | Batch-based execution | Concatenation |
| `ml_experiment` | Distributed hyperparameter search | 8 parallel experiments with tiered difficulty | Custom ML ranking |
| `image_processing` | Batch image analysis | URL list splitting across workers | Distributed merge |
| `web_scraping` | Parallel URL scraping | URL list splitting across workers | Distributed merge |
| `audio_transcription` | Parallel audio file transcription | URL list splitting across workers | Distributed merge |
| `sentiment_classification` | Text sentiment analysis at scale | Text list splitting across workers | Sentiment-aware merge |

## ML Experiment System

The ML experiment pipeline is a first-class task type that runs distributed hyperparameter search:

- **14 model types**: LinearRegression, Ridge, DecisionTree, RandomForest, GradientBoosting (regression and classification variants)
- **Synthetic datasets**: 75K-row `weather_ri` (16 features, regression) and `customer_churn` (12 features, classification) with realistic nonlinear relationships
- **Parallel execution**: Planner generates 8 experiments per job with different model configs and hyperparameters
- **Tiered difficulty**: Tasks tagged min_tier 1-4 so heavy models (500-tree forests, tuned gradient boosting) route to capable workers
- **5-fold cross-validation** with full metrics (R2, MSE, MAE for regression; F1, accuracy, precision, recall for classification)
- **Auto-ranking aggregation**: Parses JSON metrics from each experiment, ranks models, produces comparison table and reusable config

### Resource Guards

- `safe_n_jobs()` reserves 2 CPU cores for the OS during parallel training
- `safe_dataset_size()` caps rows based on available RAM (25K rows/GB, floor 5K) to prevent OOM

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

- **jobs** -- id (UUID), title, description, task_type, input_payload (JSONB), status, priority, final_output, created_at
- **job_tasks** -- id, job_id (FK CASCADE), task_order, task_name, task_payload (JSONB), status, worker_node_id, started_at
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
    AND COALESCE((jt.task_payload->>'min_tier')::int, 1) <= $2
  ORDER BY j.priority DESC,
           COALESCE((jt.task_payload->>'min_tier')::int, 1) DESC,
           jt.created_at
  LIMIT 1
  FOR UPDATE OF jt SKIP LOCKED
) RETURNING *
```

- `FOR UPDATE SKIP LOCKED` prevents race conditions across concurrent workers
- Priority ordering: job priority DESC, task tier DESC (hard tasks first), FIFO within tier
- Workers pass their tier level; system only assigns tasks they can handle

### Worker Resilience

- **Exponential backoff**: 5s, 15s, 30s retry waits
- **Rate-limit detection**: Doubles wait on 429/rate/quota errors
- **4 total attempts** before marking task failed
- **Heartbeat-based liveness**: 30-second heartbeat window; workers marked offline if stale

### Background Maintenance

A background loop runs every 60 seconds:
- **Stale task reaper**: Tasks running >8 minutes are requeued (status reset, worker cleared)
- **Dead worker pruner**: Workers with no heartbeat for >1 hour are removed
- Events logged for every requeue (`task_requeued`)

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
| GET | `/` | Serve frontend |
| GET | `/health` | Health check (verifies DB connection) |
| GET | `/jobs` | List all jobs |
| GET | `/jobs/{job_id}` | Get single job |
| POST | `/jobs` | Create job and plan subtasks (transactional) |
| GET | `/jobs/{job_id}/tasks` | Get job tasks |
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

## Frontend

Single-page app with dark theme UI:
- **Dynamic form**: Input fields change based on task type (URL input for codebase review, dataset selector for ML, textarea for text tasks)
- **Task descriptions**: Each type shows "How it works" and "Why DCN at scale" context
- **Live polling**: 1.5s interval updates status badge, task list, and progress bar
- **Dual output rendering**: HTML outputs get iframe preview and source tabs; markdown rendered via marked.js
- **10 task type support** with type-specific payload construction

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
│   │   ├── jobs.py          # Job CRUD and creation pipeline
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
│   └── public_page/
│       └── index.html       # Full SPA (712 lines, dark theme)
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
uvicorn main:app --host 0.0.0.0 --port 8000

# In separate terminals, start workers:
python -m workers.worker
```

## Task Status Flow

```
queued --> running --> submitted --> (aggregation check) --> job completed
               \--> failed
               \--> (stale >8min) --> requeued --> claimed by another worker
```
