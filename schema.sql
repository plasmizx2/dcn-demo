-- DCN Demo — Database Schema (matches Supabase production)
-- Run this against a fresh PostgreSQL/Supabase database to create all tables.
-- Safe to re-run: uses IF NOT EXISTS.

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ─── Jobs ───────────────────────────────────────────────
-- user_id must reference dcn_users(id) when using OAuth (see backend/main.py migration).
-- Legacy DBs may still point at public.users; startup migrates that FK.
CREATE TABLE IF NOT EXISTS jobs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID,
    title               TEXT NOT NULL,
    description         TEXT,
    task_type           TEXT NOT NULL,
    input_payload       JSONB NOT NULL DEFAULT '{}',
    output_payload      JSONB,
    status              TEXT NOT NULL DEFAULT 'queued',
    priority            INTEGER NOT NULL DEFAULT 1,
    reward_amount       NUMERIC NOT NULL DEFAULT 0.00,
    requires_validation BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    final_output        TEXT
);

-- ─── Job Tasks (subtasks) ───────────────────────────────
CREATE TABLE IF NOT EXISTS job_tasks (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id              UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    task_order          INTEGER,
    task_name           TEXT NOT NULL,
    task_description    TEXT,
    task_payload        JSONB NOT NULL DEFAULT '{}',
    assigned_worker_id  UUID,
    status              TEXT NOT NULL DEFAULT 'queued',
    started_at          TIMESTAMPTZ,
    completed_at        TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    worker_node_id      UUID,
    claim_after         TIMESTAMPTZ,
    failure_count       INTEGER NOT NULL DEFAULT 0
);

-- ─── Job Events (event log) ─────────────────────────────
CREATE TABLE IF NOT EXISTS job_events (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id              UUID,
    task_id             UUID,
    event_type          TEXT NOT NULL,
    message             TEXT NOT NULL,
    metadata            JSONB NOT NULL DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─── Task Results ───────────────────────────────────────
CREATE TABLE IF NOT EXISTS task_results (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id                 UUID NOT NULL REFERENCES job_tasks(id) ON DELETE CASCADE,
    worker_id               UUID,
    worker_node_id          UUID,
    result_payload          JSONB NOT NULL DEFAULT '{}',
    result_text             TEXT,
    execution_time_seconds  NUMERIC,
    status                  TEXT NOT NULL DEFAULT 'submitted',
    submitted_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─── Worker Nodes ───────────────────────────────────────
CREATE TABLE IF NOT EXISTS worker_nodes (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID,
    node_name           TEXT NOT NULL,
    machine_type        TEXT,
    status              TEXT NOT NULL DEFAULT 'offline',
    cpu_cores           INTEGER,
    ram_gb              INTEGER,
    gpu_name            TEXT,
    location            TEXT,
    last_heartbeat      TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─── Indexes ────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_job_tasks_job_id ON job_tasks(job_id);
CREATE INDEX IF NOT EXISTS idx_job_tasks_status ON job_tasks(status);
CREATE INDEX IF NOT EXISTS idx_job_events_job_id ON job_events(job_id);
CREATE INDEX IF NOT EXISTS idx_task_results_task_id ON task_results(task_id);
CREATE INDEX IF NOT EXISTS idx_worker_nodes_status ON worker_nodes(status);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_priority ON jobs(priority DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_user_id ON jobs(user_id);
CREATE INDEX IF NOT EXISTS idx_job_tasks_claim_after ON job_tasks(claim_after) WHERE claim_after IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs(created_at DESC);

-- ─── Caching ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS llm_cache (
    prompt_hash         TEXT PRIMARY KEY,
    response_text       TEXT NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─── Auth ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS dcn_users (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email               TEXT UNIQUE NOT NULL,
    name                TEXT,
    avatar_url          TEXT,
    provider            TEXT NOT NULL,
    provider_id         TEXT NOT NULL,
    role                TEXT NOT NULL DEFAULT 'customer',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(provider, provider_id)
);

CREATE TABLE IF NOT EXISTS sessions (
    token_id            TEXT PRIMARY KEY,
    user_id             UUID NOT NULL REFERENCES dcn_users(id) ON DELETE CASCADE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
