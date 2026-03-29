# DCN: Distributed Compute Network for AI Task Orchestration

## Vision
DCN is a distributed AI orchestration system that converts high-level tasks into parallel execution pipelines across multiple compute nodes.

Instead of manually defining workflows or running AI tasks sequentially, DCN:
- decomposes tasks automatically
- distributes execution across workers
- aggregates results into structured outputs

The long-term vision is a shared compute network where users submit tasks and distributed nodes execute work in exchange for incentives.

The current hackathon implementation focuses on a working distributed execution engine with real-time visibility and measurable performance gains.

---

## What We Are Building
DCN has three user-facing layers:

1. Public job submission at `/`
2. Operator monitoring at `/ops`
3. Results browsing at `/results`

A user submits a job, the planner decomposes it into subtasks, workers claim and execute those subtasks in parallel, and the aggregator produces the final output. The UI then shows both the result and the timing difference between sequential and distributed execution.

---

## Core Demo
The hero demo is the `ml_experiment` pipeline.

A user selects a dataset and submits an ML experiment job. The system generates multiple model-training experiments with different models and hyperparameters, distributes them across workers, ranks the results, and returns the best-performing configuration with a comparison table.

Supporting demos are:
- `document_analysis`
- `codebase_review`

These prove that the same orchestration engine generalizes to other task types.

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

For document analysis:
- sequential execution: about 50 seconds
- distributed execution with 5 workers: about 12 seconds

This is about a 4x speedup and serves as the clearest demonstration of DCN’s value proposition.

---

## System Architecture

### 1. Job System
Users submit a job with:
- task type
- input payload

The backend creates the job and stores its metadata.

### 2. Planner
The planner decomposes the job into subtasks using task-type-specific strategies.

Supported task types:
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
- document analysis uses chunk merge and synthesis
- codebase review produces a structured report
- website builder assembles HTML sections
- research pipeline merges phases
- sentiment classification aggregates counts
- ml_experiment ranks model results and returns a best configuration

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

### document_analysis
The planner examines input length and paragraph structure, then splits the document into 1–6 actual chunks based on content size. Each task includes real chunk text in `task_payload` so workers process distinct parts of the document rather than placeholder sections.

### codebase_review
The planner creates focused review tasks that target different concerns such as core logic, architecture, and security/quality. These tasks use repo-specific descriptions instead of generic placeholders.

### website_builder
The planner parses the user request for section keywords such as hero, pricing, features, or footer. If no strong section hints are found, it falls back to a standard multi-section layout.

### research_pipeline
The planner generates structured research phases such as landscape survey, deep analysis, critical evaluation, and future outlook.

### data_processing
The planner looks at actual record count and splits the input into 1–6 data batches. Each task receives its own slice of the dataset through `task_payload`.

### ml_experiment
The planner generates multiple experiment configurations with different models and hyperparameters so workers can train and evaluate them in parallel.

This makes the planner more than a lookup table: it is a deterministic decomposition layer that uses real input size, structure, and task type to generate executable subtasks.

---

## Handler Design

Handlers consume task-specific data from `task_payload` first, and fall back to the original job payload only if needed.

This allows:
- document workers to analyze their assigned chunk
- data-processing workers to operate on their assigned batch
- website workers to generate the correct section
- research workers to focus on their assigned phase

This keeps execution aligned with planner decomposition.

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
The current design is suitable for hackathon-scale distributed execution.

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

For the hackathon, the important point is that the internal boundaries between planner, workers, and aggregator already make this evolution possible.

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

Fallback milestone:
- if breadth becomes a risk, focus on:
  - ml_experiment
  - document_analysis
  - codebase_review

Depth is prioritized over breadth.

---

## Risks
### Main Risks
- AI API instability or rate limits
- worker desynchronization
- shallow implementation across too many task types
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
- results browsing at `/results`
- timing comparison
- ML experiment hero demo

The plan is intentionally aligned to the current build and does not rely on hosted deployment claims.
