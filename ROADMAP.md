# DCN Roadmap: ML Experiment Platform → Distributed Compute Network

## North Star
A self-hosted ML experiment runner where anyone can contribute compute.
You run the coordinator. Your friends run workers on their PCs. Jobs get distributed automatically.

---

## Current State (What Already Works)

- Job submission → planner → subtasks → workers → aggregation pipeline
- `ml_experiment` handler with sklearn models, cross-validation, ranked output
- `dcn-worker/` desktop app that connects to a remote coordinator over HTTP
- PostgreSQL row-locking for race-condition-free task claiming
- Worker registration, heartbeat, tier detection

The distributed worker architecture already exists. The gap is focus and polish.

---

## Phase 0: Strip to ML Experiment Only

Remove everything that isn't `ml_experiment`. This reduces scope, sharpens the product, and makes every subsequent step simpler.

### What to remove
- [ ] Task types from `backend/config.py`: `document_analysis`, `codebase_review`, `website_builder`, `research_pipeline`, `data_processing`, `image_processing`, `web_scraping`, `audio_transcription`, `sentiment_classification`
- [ ] Handler files: `backend/handlers/document.py`, `codebase.py`, `website.py`, `research.py`, `data_processing.py`
- [ ] Desktop worker handlers: `dcn-worker/handlers/audio_transcription.py`, `image_processing.py`, `sentiment_classification.py`, `web_scraping.py`
- [ ] Planner branches for removed task types (`backend/planner.py`)
- [ ] Aggregator branches for removed task types (`backend/aggregator.py`)
- [ ] Frontend task type selectors (document, codebase, website, research, data options)
- [ ] Gemini client (used only for non-ML task synthesis — ML handler uses sklearn directly)

### What stays
- `ml_experiment` handler (backend + dcn-worker)
- Full planner → worker → aggregator pipeline
- Coordinator server, job API, worker API
- Operator dashboard (`/ops`)
- Results page (`/results`)
- `dcn-worker/` desktop app

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
- [ ] Extract `dcn-worker/` into a standalone pip-installable package
- [ ] Create `dcn_worker/__main__.py` so `python -m dcn_worker` works
- [ ] `--host`, `--name`, `--task-types` CLI flags
- [ ] Auto-detect hardware tier on startup (already exists in `hardware.py`)
- [ ] Print clear status on connect: `Connected to coordinator. Waiting for jobs...`
- [ ] Handle coordinator being unreachable gracefully (retry with backoff, don't crash)
- [ ] Write a one-page `WORKER_SETUP.md` — copy/paste instructions for friends

---

## Phase 2: Coordinator Easy Deploy

Your coordinator (the server) needs to be easy to run on any machine, not just your laptop.

### Goal
One command to start the full coordinator stack:
```bash
docker compose up
```

### Tasks
- [ ] Write `Dockerfile` for the backend
- [ ] Write `docker-compose.yml` with backend + Postgres
- [ ] Environment variable config: `DATABASE_URL`, `PORT`, `SECRET_KEY`
- [ ] Health check endpoint (`/health`) so workers can verify connectivity
- [ ] `COORDINATOR_SETUP.md` — how to run the coordinator on a VPS or spare machine

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

## Phase 4: Real ML Support

The current handler uses sklearn on hardcoded datasets. Real ML engineers need to bring their own data and models.

### Goal
Users can upload a CSV and pick from supported model families. Workers train on real data.

### Tasks
- [ ] Job submission accepts CSV file upload or URL
- [ ] Planner generates experiment configs from user-specified model list + param grid
- [ ] Worker handler loads CSV, runs train/test split, returns metrics
- [ ] Support: LinearRegression, Ridge, RandomForest, GradientBoosting, XGBoost
- [ ] Results page shows ranked experiment table with downloadable winning config
- [ ] (Later) PyTorch support — simple MLP trainer for classification tasks

---

## Phase 5: Operator Polish

The `/ops` dashboard is your demo centerpiece. It needs to show the distributed story clearly.

### Tasks
- [ ] Live worker list: name, machine, tier, tasks completed, last seen
- [ ] Per-worker task activity feed
- [ ] Job timeline: submitted → planned → tasks distributed → aggregated
- [ ] Speedup stat: "This job ran in 12s distributed vs ~50s sequential"
- [ ] Worker geographic map (optional, use IP geolocation — shows "compute from multiple machines")

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

1. Complete Phase 0 — strip to `ml_experiment` only
2. Test the pipeline end-to-end with just ML experiments
3. Get `dcn-worker` running on a second machine (your other laptop)
4. Run a real job across two machines and screenshot the `/ops` dashboard

That's the MVP of a distributed compute network.
