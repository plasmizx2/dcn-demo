# DCN: Distributed Compute Network for AI Task Orchestration

## Vision
DCN is a distributed AI orchestration system that converts high-level tasks into parallel execution pipelines across multiple compute nodes.

Instead of manually defining workflows or running AI tasks sequentially, DCN:
- decomposes tasks automatically
- distributes execution across workers
- aggregates results into structured outputs

The long-term vision is a shared compute network where users submit tasks and distributed nodes execute work in exchange for incentives.

The current implementation focuses on a working distributed execution engine with real-time visibility and measurable performance gains.

---

## What We Are Building
DCN has three user-facing layers:

1. Public job submission at `/`
2. Operator monitoring at `/ops`
3. All jobs (admin) at `/jobs` (`/results` redirects)

A user submits a job, the planner decomposes it into subtasks, workers claim and execute those subtasks in parallel, and the aggregator produces the final output. The UI then shows both the result and the timing difference between sequential and distributed execution.

---

## Core Demo
The hero demo is the `ml_experiment` pipeline.

A user selects a dataset and submits an ML experiment job. The system generates multiple model-training experiments with different models and hyperparameters, distributes them across workers, ranks the results, and returns the best-performing configuration with a comparison table.

This is currently the only fully implemented task type. The architecture supports adding more task types (each with its own planner strategy, handler, and aggregation logic), but depth on `ml_experiment` is prioritized over breadth across many shallow implementations.

---

## Problem
Current AI workflows are often:
- sequential
- manually orchestrated
- limited by one machine or one process
- difficult to compare when multiple strategies are involved

For example:
- a large document is analyzed sequentially
- a repo is reviewed one section at a time
- ML models are trained one by one and compared manually

DCN addresses this by:
- decomposing work automatically
- distributing tasks across workers
- aggregating outputs into a final structured result

---

## Real-World Scenario
A developer wants to evaluate multiple ML models on a dataset.

Without DCN:
- experiments run one by one
- results must be manually compared
- total time grows linearly with each additional experiment

With DCN:
- the planner generates multiple experiment tasks
- workers process them in parallel
- results are ranked automatically
- the final output identifies the best model and configuration

This turns a manual experimentation workflow into an automated distributed pipeline.

---

## Benchmark
The current system includes a sequential-vs-distributed timing comparison.

For ML experiments with multiple model configurations:
- sequential execution scales linearly with each additional experiment
- distributed execution with multiple workers processes experiments in parallel

The timing comparison on completed jobs serves as the clearest demonstration of DCN’s value proposition.

---

## System Architecture

### 1. Job System
Users submit a job with:
- task type
- input payload

The backend creates the job and stores its metadata.

### 2. Planner
The planner decomposes the job into subtasks using task-type-specific strategies.

Currently implemented task type:
- ml_experiment

The planner includes a generic fallback for unknown task types, but only `ml_experiment` has a full handler, planner strategy, and aggregation pipeline.

### 3. Worker Pool
Workers:
- poll for tasks
- claim tasks atomically
- execute independently
- submit results

Task claiming uses `SELECT ... FOR UPDATE SKIP LOCKED`, which prevents two workers from claiming the same task.

### 4. Aggregator
The aggregator combines results after all subtasks are complete.

Aggregation is task-type-specific:
- ml_experiment ranks model results and returns a best configuration

Future task types would add their own aggregation strategies.

### 5. Monitoring
The operator dashboard at `/ops` shows:
- jobs
- worker activity
- task states
- queue status
- event timeline
- timing comparison for completed jobs

This makes the orchestration visible during the demo.

---

## Planner Design

The planner is task-type-aware and decomposes jobs differently depending on the workflow.

### ml_experiment
The planner generates multiple experiment configurations with different models and hyperparameters so workers can train and evaluate them in parallel. It selects model families based on the dataset's task type (regression vs classification) and creates one subtask per experiment.

The planner is a deterministic decomposition layer that uses real input structure and task type to generate executable subtasks. Future task types would add their own planner strategies here.

---

## Handler Design

Handlers consume task-specific data from `task_payload` first, and fall back to the original job payload only if needed.

Currently only the `ml_experiment` handler is implemented. It trains the assigned model on the dataset, runs cross-validation, and returns structured metrics. Future task types would add their own handlers following the same pattern.

---

## Technical Depth

### Concurrency Model
DCN uses PostgreSQL row-level locking to coordinate worker claims safely:
- `FOR UPDATE SKIP LOCKED`
- one worker per task
- no race conditions between claimers

### Scheduling
Tasks are prioritized using:
- job priority
- task difficulty tier
- creation order

Workers only claim tasks they are capable of handling.

### Reliability
The system includes:
- retry logic with exponential backoff
- rate-limit detection
- stale task handling
- worker heartbeat tracking
- event-sourced lifecycle logging

### Event Tracking
Lifecycle events include:
- `job_created`
- `task_split`
- `task_started`
- `task_submitted`
- `job_completed`

This provides observability for both debugging and demo clarity.

---

## Distributed ML Experiment Pipeline
The `ml_experiment` mode is the most technically sophisticated workflow in the project.

### Flow
1. User selects a dataset and submits an ML experiment job
2. Planner generates multiple experiments with different models and hyperparameters
3. Workers train models independently
4. Each worker returns structured metrics
5. Aggregator ranks all experiments and returns the best result

### Included Model Families
The repo currently supports multiple regression and classification models, including:
- LinearRegression
- Ridge
- DecisionTree
- RandomForest
- GradientBoosting

### Datasets
The current build includes:
- a synthetic weather dataset
- a customer churn dataset

### Evaluation
The ML flow includes:
- train/test split
- 5-fold cross-validation
- multi-metric output
- ranked comparison
- reusable winning configuration

This makes ML experimentation the strongest proof of distributed execution in the project.

---

## Innovation
DCN’s main innovation is not the existence of workers or queues by themselves. Those patterns already exist.

The novelty is in the combination of:
- task-type-aware automatic decomposition
- AI-native execution
- built-in aggregation
- real-time orchestration visibility
- a unified interface for multiple classes of AI workloads

Compared to traditional workflow tools, the user does not manually define a DAG or pipeline. They submit a high-level job, and the system handles decomposition, execution, and aggregation for them.

---

## Market Awareness
Relevant systems include:
- LangGraph
- CrewAI
- Prefect
- Temporal
- Ray
- AWS Step Functions

These tools are strong, but they tend to emphasize one of:
- workflow definition
- agent coordination
- infrastructure orchestration
- distributed compute primitives

DCN is positioned differently:
- AI execution and orchestration are combined in one system
- aggregation is a first-class component
- the user experience is centered on “submit one task, get one result”
- the demo makes performance gains visible through timing comparison

DCN is not trying to replace all workflow engines. It is trying to make distributed AI task execution easier to use and easier to demonstrate.

---

## Differentiation
DCN differentiates itself through four things:

1. No explicit workflow authoring for the user
2. Built-in task decomposition by task type
3. Built-in aggregation of heterogeneous results
4. Real-time operator visibility into execution

The strongest differentiator in the current build is the ML experiment pipeline with ranked output and visible parallel speedup.

---

## Scalability
The current design is suitable for current-scale distributed execution.

Strengths:
- parallel worker model
- independent tasks
- modular planner/worker/aggregator architecture

Current limitation:
- database row locking is the coordination bottleneck at larger scale

Future scaling path:
- move from DB-coordinated claims to queue-based coordination
- support external worker nodes
- add hardware-aware scheduling

This gives the project a credible path beyond the demo without overstating current capabilities.

---

## Ecosystem Design
The current build is intentionally focused and does not yet implement a third-party plugin or external worker API.

However, the architecture is designed so that future versions can support:
- external worker registration
- multiple AI providers
- pluggable execution backends
- shared compute participation

For the current, the important point is that the internal boundaries between planner, workers, and aggregator already make this evolution possible.

---

## Worker repository (must mirror ML code)

The distributed **worker** is a **separate Git repo**: [github.com/plasmizx2/dcn-worker](https://github.com/plasmizx2/dcn-worker). It is not inside this repo. A typical local layout is two sibling folders, e.g. `~/Desktop/dcn-demo` (this project) and `~/Desktop/dcn-worker` (worker only).

### When Claude Code (or any agent) must update **both** repos

Apply the **same logical change** in **both** places whenever you touch:

| Area | In **this repo** (`dcn-demo`) | In **worker repo** (`dcn-worker`) |
|------|-------------------------------|-----------------------------------|
| Dataset loading, OpenML/CSV, caching, `get_dataset`, `load_external_dataset`, `preview_dataset` | `backend/datasets.py` | `datasets.py` (repo root) |
| ML training, metrics, sklearn models for `ml_experiment` | `backend/handlers/ml_experiment.py` | `handlers/ml_experiment.py` |

If only one side is edited, production workers will **drift** from the coordinator and jobs can behave differently or fail.

### When **only** `dcn-demo` needs changes

Everything that does **not** run on the worker machine: planner, API routes, auth, database, frontend, aggregator, `backend/main.py`, `backend/planner.py` (unless it only changes non-ML metadata you also document for workers), etc.

### Agent workflow (required)

1. After editing `backend/datasets.py` or `backend/handlers/ml_experiment.py`, **open the `dcn-worker` checkout** (or add it to the workspace) and **repeat the equivalent edit** in the worker paths above.
2. Commit and push **both** repositories.
3. If you cannot access the worker repo, **tell the user** explicitly: “Mirror this change in `dcn-worker` at …” with a short diff summary.

There is **no** automatic sync between repos; mirroring is intentional until a shared package exists.

---

## Team Execution Plan
Team size: 1

Build sequence:
- backend and database foundation
- planner and task decomposition
- worker execution loop
- AI integration
- aggregation
- public UI
- operator dashboard
- polish and timing visualization

Primary demo milestone:
- job → planner → workers → aggregation → final output

Hero milestone:
- fully working `ml_experiment` flow with ranked output and timing comparison

Current focus:
- ml_experiment is the only fully implemented task type
- depth on one strong pipeline is prioritized over breadth across many shallow ones

---

## Risks
### Main Risks
- AI API instability or rate limits
- worker desynchronization
- polling overhead
- DB contention at higher concurrency

### Mitigations
- retries with backoff
- atomic task claims
- task-type-specific aggregation fallbacks
- heartbeat tracking
- focusing the demo on the strongest flows

### Fallback Demo
If AI outputs are degraded, DCN can still demonstrate:
- job decomposition
- parallel worker execution
- event tracking
- timing advantage of distributed over sequential execution

---

## Alignment with Implementation
The current implementation includes:
- job submission
- planner-driven task generation
- smart task-type-aware planners
- worker claiming and execution
- task-payload-aware handlers
- aggregation into final output
- public UI at `/`
- operator dashboard at `/ops`
- all jobs browsing at `/jobs` (`/results` redirects)
- timing comparison
- ML experiment hero demo

The plan is intentionally aligned to the current build and does not rely on hosted deployment claims.
