# DCN: Distributed Compute Network for AI Task Orchestration

[![GitHub](https://img.shields.io/badge/GitHub-plasmizx2%2Fdcn--demo-181717?logo=github)](https://github.com/plasmizx2/dcn-demo)
[![Live Demo](https://img.shields.io/badge/Live_Demo-dcn--demo.onrender.com-7c3aed)](https://dcn-demo.onrender.com)
[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-async-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)

DCN is a distributed AI task orchestration system that decomposes high-level workloads into parallel subtasks, executes them across worker nodes, and aggregates the results into a unified final output.

Users submit one job and DCN handles:
- task decomposition
- scheduling
- parallel execution
- validation
- aggregation
- timing comparison

No DAG authoring, no manual orchestration, no workflow boilerplate.

Built with FastAPI, PostgreSQL, and Google Gemini.

> **Live demo**: [dcn-demo.onrender.com](https://dcn-demo.onrender.com)  
> **Source**: [github.com/plasmizx2/dcn-demo](https://github.com/plasmizx2/dcn-demo)

---

## Live Demo

Fastest way to see DCN working:

1. Open [dcn-demo.onrender.com](https://dcn-demo.onrender.com)  
2. Sign in as `admin` / `admin123`  
3. Submit an `ml_experiment` job using the `weather` dataset  
4. Open `/ops` and watch tasks fan out across workers  
5. Wait for completion and inspect:
   - ranked model leaderboard
   - best model selection
   - parallel vs sequential timing comparison

Best supporting demos:
- `document_analysis`
- `codebase_review`

---

## Why DCN

Most AI workflows are still:
- sequential
- manually orchestrated
- hard to compare
- limited by one machine or one process

DCN changes that by taking a single high-level request and turning it into a distributed execution pipeline automatically.

### Core idea
**Submit one job → get one result**  
DCN handles everything in between.

---

## Hero Demo: Distributed ML Experimentation

The strongest demo flow is `ml_experiment`.

DCN:
- generates multiple model configurations
- distributes them across workers
- evaluates them in parallel
- ranks all results
- returns the best model and configuration

### What happens
1. User submits an `ml_experiment` job
2. Planner creates 8 parallel experiment tasks
3. Workers claim experiments based on capability tier
4. Each worker trains and evaluates a model independently
5. Aggregator ranks the results and highlights the winner

### Why this is the best demo
It makes distributed execution obvious:
- multiple independent tasks
- visible worker activity
- measurable speedup
- structured output judges can understand instantly

---

## Performance Proof

DCN exposes real timing comparisons in the UI.

Example benchmark:
- Sequential execution: ~50s
- Distributed execution (5 workers): ~12s

Result:
- ~4x speedup

The system computes:
- **Sequential time** = sum of all task execution times
- **Parallel time** = wall-clock distributed execution time
- **Speedup** = sequential / parallel

This is shown directly in both the public UI and the operator dashboard.

---

## Architecture

```text
User submits job
      |
   Planner
(task decomposition)
      |
+-----+-----+-----+-----+
|     |     |     |     |
W1    W2    W3    WN   ...
|     |     |     |     
+-----+-----+-----+-----+
      |
  Aggregator
      |
 Final Output
      |
Timing + Results UI