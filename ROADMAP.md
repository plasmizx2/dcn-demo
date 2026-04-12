# DCN Roadmap: ML Experiment Platform → Distributed Compute Network

## North Star
A self-hosted ML experiment runner where anyone can contribute compute.
You run the coordinator. Your friends run workers on their PCs. Jobs get distributed automatically.

---

## Current State (What Already Works)

- Job submission → planner → subtasks → workers → aggregation pipeline
- `ml_experiment` handler with sklearn models, cross-validation, ranked output
- [`dcn-worker` repo](https://github.com/plasmizx2/dcn-worker) — desktop/CLI worker that connects to the coordinator over HTTP
- PostgreSQL row-locking for race-condition-free task claiming
- Worker registration, heartbeat, tier detection

The distributed worker architecture already exists. The gap is focus and polish.

---

## Phase 0: Strip to ML Experiment Only ✅ COMPLETE

Non-ML task types and handlers have been removed. Only `ml_experiment` remains.

### What stays
- `ml_experiment` handler (backend + [dcn-worker](https://github.com/plasmizx2/dcn-worker))
- Full planner → worker → aggregator pipeline
- Coordinator server, job API, worker API
- Operator dashboard (`/ops`)
- All jobs page (`/jobs`; `/results` redirects)
- [dcn-worker](https://github.com/plasmizx2/dcn-worker) desktop app

---

## Phase 1: One-Command Worker Install

Right now someone has to clone the repo to run a worker. That's too much friction.

### Goal
A friend should be able to run one command and become a worker node:
```bash
pip install dcn-worker
dcn-worker --host http://your-server.com --name "mikes-pc"
```

### Tasks
- [x] Standalone worker repo ([dcn-worker](https://github.com/plasmizx2/dcn-worker))
- [ ] Publish as a pip-installable package (`pip install dcn-worker`)
- [ ] Create `dcn_worker/__main__.py` so `python -m dcn_worker` works
- [ ] `--host`, `--name`, `--task-types` CLI flags
- [ ] Auto-detect hardware tier on startup (already exists in `hardware.py`)
- [ ] Print clear status on connect: `Connected to coordinator. Waiting for jobs...`
- [ ] Handle coordinator being unreachable gracefully (retry with backoff, don't crash)
- [ ] Write a one-page `WORKER_SETUP.md` — copy/paste instructions for friends

---

## Phase 2: Coordinator Easy Deploy ✅ COMPLETE

### Done
- [x] `Dockerfile` for production build (Vite/React + FastAPI)
- [x] `render.yaml` for one-click Render deployment
- [x] Environment variable config: `DATABASE_URL`, `PORT`, `SECRET_KEY`
- [x] Health check endpoint (`/health`)

### Remaining
- [ ] `docker-compose.yml` with backend + Postgres (for local self-hosting)
- [ ] `COORDINATOR_SETUP.md` — how to run on a VPS or spare machine

---

## Phase 3: Worker Auth

Right now anyone who knows your coordinator URL can register as a worker and claim jobs. For a private network (you + friends) this needs a token.

### Goal
Workers authenticate with a secret token. Unknown workers are rejected.

### Tasks
- [ ] Add `worker_token` to coordinator config (env var)
- [ ] Workers pass token in `Authorization` header on all requests
- [ ] Coordinator rejects requests with missing/wrong token with `401`
- [ ] Token displayed on coordinator dashboard so you can share it with friends
- [ ] `dcn-worker` CLI accepts `--token` flag

---

## Phase 4: Real ML Support ✅ MOSTLY COMPLETE

### Done
- [x] Job submission accepts CSV file upload, OpenML ID, or built-in datasets
- [x] Planner generates experiment configs from user-specified model list + param grid
- [x] Worker handler loads CSV, runs train/test split, returns metrics
- [x] Support: LinearRegression, Ridge, DecisionTree, RandomForest, GradientBoosting
- [x] Results page shows ranked experiment table with downloadable winning config

### Remaining
- [ ] Target column dropdown from preview columns (#78)
- [ ] XGBoost support
- [ ] PyTorch support (future)

---

## Phase 5: Operator Polish ✅ MOSTLY COMPLETE

### Done
- [x] Live worker list: name, machine, tier, tasks completed, last seen
- [x] Per-worker task activity feed
- [x] Job timeline: submitted → planned → tasks distributed → aggregated
- [x] Speedup stat: timing comparison tab on completed jobs

### Remaining
- [ ] Worker geographic map (optional, future)

---

## Phase 6: Public Beta

Once a few friends are running workers and jobs complete reliably, open it up.

### Goal
Anyone can submit an ML experiment job. Anyone can run a worker and contribute compute.

### Tasks
- [ ] Landing page explains the model clearly: "submit jobs, contribute compute"
- [ ] Worker leaderboard: who has contributed the most compute
- [ ] Basic job history per user (requires auth)
- [ ] Rate limiting on job submission to prevent abuse
- [ ] Decide: credits system, or just goodwill for Phase 6

---

## What This Is Not (Yet)

- Not a GPU cluster — sklearn/CPU models only until Phase 4+
- Not a marketplace — no payments until you validate the model
- Not a managed SaaS — self-hosted first, hosted tier comes later

---

## Immediate Next Steps

1. Fix P1 bugs: contact form email validation (#59), long task names in worker-logs (#60), billing regressions (#98, #116)
2. Complete P1 enhancements: target column dropdown (#78), pricing credibility (#74), task requeue on worker disconnect (#82)
3. Work through P2 items: pagination (#56), security hardening (#86), README refresh (#84)

See [GitHub issue #88](https://github.com/plasmizx2/dcn-demo/issues/88) for the full prioritized production readiness checklist.
