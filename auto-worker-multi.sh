#!/bin/bash
# Multi-repo auto-worker runner.
#
# Runs the repo-scoped core worker once per configured repo.
#
# Usage:
#   ./auto-worker-multi.sh [path/to/auto-worker.repos.json]
#
# Env:
# - AUTO_WORKER_HOME: where to store per-repo state/log/lock (default: ~/.auto-worker)
# - DRY_RUN=1: skip push + PR create across all repos
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG_PATH="${1:-${ROOT_DIR}/auto-worker.repos.json}"
AUTO_WORKER_HOME="${AUTO_WORKER_HOME:-$HOME/.auto-worker}"
DRY_RUN="${DRY_RUN:-0}"

if [ ! -f "$CONFIG_PATH" ]; then
  echo "Config not found: $CONFIG_PATH" >&2
  exit 1
fi

for c in jq git gh; do
  command -v "$c" >/dev/null 2>&1 || { echo "auto-worker-multi requires '$c' on PATH" >&2; exit 1; }
done

mkdir -p "$AUTO_WORKER_HOME"

CORE="${ROOT_DIR}/auto-worker-core.sh"
if [ ! -f "$CORE" ]; then
  echo "Core worker not found: $CORE" >&2
  exit 1
fi

repo_count="$(jq -r '.repos | length' "$CONFIG_PATH")"
if [ "${repo_count}" = "null" ] || [ "${repo_count}" -lt 1 ]; then
  echo "No repos found in config: $CONFIG_PATH" >&2
  exit 1
fi

echo "auto-worker-multi: ${repo_count} repo(s), DRY_RUN=${DRY_RUN}, home=${AUTO_WORKER_HOME}"

for i in $(seq 0 $((repo_count - 1))); do
  name="$(jq -r ".repos[$i].name // \"\"" "$CONFIG_PATH")"
  path="$(jq -r ".repos[$i].path" "$CONFIG_PATH")"
  skip_issue_numbers="$(jq -r ".repos[$i].skip_issue_numbers // \"\"" "$CONFIG_PATH")"
  roadmap_issue_number="$(jq -r ".repos[$i].roadmap_issue_number // \"\"" "$CONFIG_PATH")"

  if [ -z "$name" ] || [ "$name" = "null" ]; then
    # stable name fallback from path basename
    name="$(basename "$path" | tr ' ' '-')"
  fi

  if [ -z "$path" ] || [ "$path" = "null" ]; then
    echo "Skipping entry $i: missing path"
    continue
  fi

  if [ ! -d "$path/.git" ]; then
    echo "Skipping ${name}: not a git repo at ${path}"
    continue
  fi

  repo_home="${AUTO_WORKER_HOME}/${name}"
  mkdir -p "$repo_home"

  export REPO_DIR="$path"
  export LOG_FILE="${repo_home}/auto-worker.log"
  export STATE_FILE="${repo_home}/state.json"
  export LOCK_FILE="${repo_home}/lock"
  export DRY_RUN
  export SKIP_ISSUE_NUMBERS="${skip_issue_numbers}"
  # Model routing:
  # - dcn-demo, dcn-worker, PeaPod: prefer Claude (then Gemini)
  # - everything else: Gemini primary, Ollama fallback if rate-limited
  if [ "$name" = "dcn-demo" ] || [ "$name" = "dcn-worker" ] || [ "$name" = "PeaPod" ]; then
    export PREFER_CLAUDE="1"
  else
    export PREFER_CLAUDE="0"
  fi
  if [ -n "$roadmap_issue_number" ] && [ "$roadmap_issue_number" != "null" ]; then
    export ROADMAP_ISSUE_NUMBER="${roadmap_issue_number}"
  else
    export ROADMAP_ISSUE_NUMBER=""
  fi

  echo "---- ${name} ----"
  # Don't let a single repo failure prevent other repos from running.
  if ! bash "$CORE"; then
    echo "Repo ${name}: run failed (see ${LOG_FILE})"
  fi
done

