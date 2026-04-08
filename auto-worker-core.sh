#!/bin/bash
# Auto Issue Worker (repo-scoped core)
# Usage: set REPO_DIR + STATE_FILE/LOG_FILE/LOCK_FILE and run.
#
# Required env:
# - REPO_DIR: absolute path to git repo
# - STATE_FILE: per-repo state json path
# - LOG_FILE: per-repo log path
# - LOCK_FILE: per-repo lock path
#
# Optional env:
# - DRY_RUN=1 (skip git push + PR create)
# - BRANCH_PREFIX (default: fix/issue-)
# - SKIP_ISSUE_NUMBERS (comma-separated, e.g. "88,123")
# - PRIORITY_LABEL_PREFIXES (comma-separated, default: P0,P1,P2,P3)
# - ROADMAP_ISSUE_NUMBER (default empty)
#
# Secrets: DO NOT hardcode. Provide via environment:
# - GH_TOKEN (required for non-interactive git push + gh api)
# - CLAUDE_CODE_OAUTH_TOKEN / GEMINI_API_KEY / etc. (as needed by your agent CLIs)
set -euo pipefail

export PATH="${PATH:-/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin}"

REPO_DIR="${REPO_DIR:?REPO_DIR is required}"
STATE_FILE="${STATE_FILE:?STATE_FILE is required}"
LOG_FILE="${LOG_FILE:?LOG_FILE is required}"
LOCK_FILE="${LOCK_FILE:?LOCK_FILE is required}"

DRY_RUN="${DRY_RUN:-0}"
BRANCH_PREFIX="${BRANCH_PREFIX:-fix/issue-}"
SKIP_ISSUE_NUMBERS="${SKIP_ISSUE_NUMBERS:-}"
PRIORITY_LABEL_PREFIXES="${PRIORITY_LABEL_PREFIXES:-P0,P1,P2,P3}"
ROADMAP_ISSUE_NUMBER="${ROADMAP_ISSUE_NUMBER:-}"
SKIP_LABELS="${SKIP_LABELS:-no-ai,needs-owner-input,needs-payment}"
PREFER_CLAUDE="${PREFER_CLAUDE:-0}"
OLLAMA_MODEL="${OLLAMA_MODEL:-}"
OLLAMA_FALLBACK_ENABLED="${OLLAMA_FALLBACK_ENABLED:-1}"
OLLAMA_P3_ONLY="${OLLAMA_P3_ONLY:-1}"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG_FILE"; }

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "auto-worker-core requires '$1' on PATH" >&2
    exit 1
  }
}

is_p3_issue_number() {
  # $1: issue number
  local n="$1"
  gh issue view "$n" --json labels --jq '[.labels[]?.name // empty] | any(startswith("P3"))' 2>/dev/null | grep -qx "true"
}

pick_first_p3_issue_number() {
  gh issue list --state open --json number,labels --jq '
    [.[] | select((.labels // []) | any(.name | startswith("P3")))] | sort_by(.number) | .[0].number // empty
  ' 2>/dev/null || true
}

create_p3_issue_from_repo_scan() {
  log "OLLAMA: no P3 issues found; creating a new P3 suggestion issue from quick scan."
  local findings
  findings="$( (command -v rg >/dev/null 2>&1 && rg -n --hidden --glob '!.git/**' 'TODO|FIXME|HACK' . || grep -R -n 'TODO\\|FIXME\\|HACK' . 2>/dev/null) | head -n 60 )"
  if [ -z "${findings:-}" ]; then
    findings="No obvious TODO/FIXME/HACK markers found in a quick scan."
  fi
  gh issue create \
    --title "P3: repo cleanup suggestions (auto)" \
    --body "$(cat <<EOF
Auto-worker reached Ollama fallback mode and did not find any open P3 issues to work on.

## Quick scan findings (first 60 matches)
\`\`\`
${findings}
\`\`\`
EOF
)" \
    --label "P3" 2>>"$LOG_FILE" || true
}

pick_ollama_model() {
  # Prefer explicit OLLAMA_MODEL; otherwise choose a deterministic installed model.
  if [ -n "$OLLAMA_MODEL" ]; then
    echo "$OLLAMA_MODEL"
    return 0
  fi
  if ! command -v ollama >/dev/null 2>&1; then
    echo ""
    return 0
  fi
  # `ollama list` columns: NAME ID SIZE MODIFIED
  # NOTE: if the Ollama server isn't reachable, `ollama list` prints an error to stderr.
  # We capture stderr so the caller can decide what to do.
  local out
  out="$(ollama list 2>&1 || true)"
  if echo "$out" | grep -qiE "could not connect|connection refused|dial tcp|failed to connect"; then
    echo ""
    return 0
  fi
  local names
  names="$(printf "%s\n" "$out" | awk 'NR>1 {print $1}' || true)"
  # Prefer known-good models on your machine.
  if echo "$names" | grep -qx "qwen2.5:7b"; then
    echo "qwen2.5:7b"
    return 0
  fi
  if echo "$names" | grep -qx "qwen2.5:3b"; then
    echo "qwen2.5:3b"
    return 0
  fi
  echo "$names" | head -n 1
}

run_ollama_agent() {
  # $1: prompt text
  local prompt="$1"
  if [ "$OLLAMA_FALLBACK_ENABLED" != "1" ]; then
    log "OLLAMA: fallback disabled (OLLAMA_FALLBACK_ENABLED=${OLLAMA_FALLBACK_ENABLED})"
    return 1
  fi
  if ! command -v ollama >/dev/null 2>&1; then
    log "OLLAMA: not installed/on PATH"
    return 1
  fi

  # If Ollama server isn't running (common under cron/non-GUI), start it.
  if ! ollama list >/dev/null 2>&1; then
    if [ "${DRY_RUN:-0}" = "1" ]; then
      log "OLLAMA: server not reachable; DRY_RUN so not starting server."
    else
      log "OLLAMA: server not reachable; starting 'ollama serve' in background..."
      (nohup ollama serve >/dev/null 2>&1 &)
      # Give it a moment, then continue (model picking will retry).
      sleep 1
    fi
  fi

  local model
  model="$(pick_ollama_model)"
  if [ -z "$model" ]; then
    log "OLLAMA: no installed models found OR server unreachable. To prove models exist, run: ollama list"
    return 1
  fi
  log "OLLAMA: running model=${model}"
  # Feed prompt on stdin to avoid shell escaping issues.
  printf "%s" "$prompt" | ollama run "$model" 2>&1 | tee -a "$LOG_FILE" || true
  return 0
}

ensure_log_dir() {
  local d
  d="$(dirname "$LOG_FILE")"
  mkdir -p "$d" 2>/dev/null || true
  touch "$LOG_FILE" 2>/dev/null || true
}

git_default_branch() {
  local d="$1"
  if git -C "$d" show-ref -q refs/remotes/origin/main 2>/dev/null; then echo main
  elif git -C "$d" show-ref -q refs/remotes/origin/master 2>/dev/null; then echo master
  else echo main
  fi
}

skip_issue_number() {
  local n="$1"
  [ -z "$SKIP_ISSUE_NUMBERS" ] && return 1
  echo ",$SKIP_ISSUE_NUMBERS," | grep -q ",${n},"
}

issue_has_skip_label() {
  # $1: issue json
  [ -z "$SKIP_LABELS" ] && return 1
  local labels
  labels="$(echo "$1" | jq -r '[.labels[]?.name // empty] | map(ascii_downcase) | .[]' 2>/dev/null || true)"
  [ -z "$labels" ] && return 1
  local needle
  echo "$SKIP_LABELS" | tr ',' '\n' | while read -r needle; do
    needle="$(echo "$needle" | tr '[:upper:]' '[:lower:]' | xargs)"
    [ -z "$needle" ] && continue
    if echo "$labels" | grep -qx "$needle"; then
      return 0
    fi
  done
  return 1
}

pick_first_eligible_issue() {
  # Returns a single issue object (json) or empty string.
  local issues_json="$1"
  [ -z "$issues_json" ] && return 0
  echo "$issues_json" | jq -r '.[] | @base64' | while read -r b64; do
    [ -z "$b64" ] && continue
    issue="$(echo "$b64" | base64 -d)"
    n="$(echo "$issue" | jq -r '.number')"
    if skip_issue_number "$n"; then
      log "SKIP: Issue #${n} is configured to be skipped."
      continue
    fi
    if issue_has_skip_label "$issue"; then
      log "SKIP: Issue #${n} has a skip label (one of: ${SKIP_LABELS})."
      continue
    fi
    echo "$issue"
    return 0
  done
  return 0
}

has_open_autoworker_pr() {
  # One PR at a time per repo, based on branch prefix.
  gh pr list --author "@me" --json headRefName,number,title --jq \
    --arg pfx "$BRANCH_PREFIX" \
    '[.[] | select(.headRefName | startswith($pfx))] | .[0] // empty' 2>/dev/null || true
}

ensure_log_dir
cd "$REPO_DIR" || { echo "REPO_DIR not found: $REPO_DIR" >&2; exit 1; }
for c in jq gh git; do require_cmd "$c"; done

# Prevent overlapping runs (per-repo lock)
if [ -f "$LOCK_FILE" ]; then
  LOCK_PID=$(cat "$LOCK_FILE" 2>/dev/null || true)
  if [ -n "${LOCK_PID:-}" ] && kill -0 "$LOCK_PID" 2>/dev/null; then
    log "SKIP: previous run (PID $LOCK_PID) still active"
    exit 0
  fi
  rm -f "$LOCK_FILE"
fi
echo $$ > "$LOCK_FILE"
trap 'rm -f "$LOCK_FILE"' EXIT

log "START: repo=${REPO_DIR}, dry_run=${DRY_RUN}, state_file=${STATE_FILE}"

# DRY_RUN=1 means: do not mutate the repo at all (no branch creation, no agent run, no commits).
# We still compute what would be done and log it.
if [ "$DRY_RUN" = "1" ]; then
  DEFAULT_BRANCH=$(git_default_branch "$REPO_DIR")
  git checkout "$DEFAULT_BRANCH" 2>>"$LOG_FILE" || true
  git pull origin "$DEFAULT_BRANCH" 2>>"$LOG_FILE" || true

  OPEN_AUTO_PR=$(has_open_autoworker_pr)
  if [ -n "$OPEN_AUTO_PR" ]; then
    OPEN_PR_NUM=$(echo "$OPEN_AUTO_PR" | jq -r '.number')
    OPEN_PR_TITLE=$(echo "$OPEN_AUTO_PR" | jq -r '.title')
    log "DRY_RUN: would WAIT (open PR #${OPEN_PR_NUM}: ${OPEN_PR_TITLE})"
    exit 0
  fi

  ISSUES=$(gh issue list --state open --json number,title,labels --jq '
    [.[]] |
    map(select(.number != 0)) |
    def priority:
      [.labels[]?.name // empty]
      | if any(startswith("P0")) then 0
        elif any(startswith("P1")) then 1
        elif any(startswith("P2")) then 2
        elif any(startswith("P3")) then 3
        else 4 end;
    sort_by([priority, .number])
  ' 2>>"$LOG_FILE" || true)

  ISSUE="$(pick_first_eligible_issue "$ISSUES")"
  if [ -z "$ISSUE" ]; then
    log "DRY_RUN: no eligible open issues"
    exit 0
  fi

  NUMBER=$(echo "$ISSUE" | jq -r '.number')
  TITLE=$(echo "$ISSUE" | jq -r '.title')
  log "DRY_RUN: would work issue #${NUMBER}: ${TITLE} on branch ${BRANCH_PREFIX}${NUMBER}"
  exit 0
fi

# ── Check if Claude is rate limited FIRST ─────────────────────
CLAUDE_RATE_LIMITED=false
if [ -f "$LOG_FILE" ] && tail -50 "$LOG_FILE" | grep -qi "You've hit your limit\|hit your limit\|rate.limit\|resets.*am\|resets.*pm"; then
  CLAUDE_RATE_LIMITED=true
  log "Claude is rate limited. Will use Gemini for P3-low issues only."
fi

# ── Resume state if present ────────────────────────────────────
RESUMING=false
if [ -f "$STATE_FILE" ]; then
  SAVED_STATUS=$(jq -r '.status // ""' "$STATE_FILE" 2>/dev/null || echo "")
  if [ "$SAVED_STATUS" = "in_progress" ]; then
    SAVED_NUMBER=$(jq -r '.number' "$STATE_FILE")
    SAVED_BRANCH=$(jq -r '.branch' "$STATE_FILE")
    TITLE=$(jq -r '.title' "$STATE_FILE")
    BODY=$(jq -r '.body' "$STATE_FILE")
    NUMBER="$SAVED_NUMBER"
    BRANCH="$SAVED_BRANCH"
    RESUMING=true
    log "RESUME: Found interrupted work on issue #${NUMBER} (branch ${BRANCH})"
  fi
fi

DEFAULT_BRANCH=$(git_default_branch "$REPO_DIR")
git checkout "$DEFAULT_BRANCH" 2>>"$LOG_FILE" || true
git pull origin "$DEFAULT_BRANCH" 2>>"$LOG_FILE" || true

if [ "$RESUMING" = false ]; then
  # Block if there's an unmerged PR from a previous run.
  OPEN_AUTO_PR=$(has_open_autoworker_pr)
  if [ -n "$OPEN_AUTO_PR" ]; then
    OPEN_PR_NUM=$(echo "$OPEN_AUTO_PR" | jq -r '.number')
    OPEN_PR_TITLE=$(echo "$OPEN_AUTO_PR" | jq -r '.title')
    log "WAIT: PR #${OPEN_PR_NUM} (${OPEN_PR_TITLE}) is still open. Merge or close it before I start the next issue."
    exit 0
  fi

  log "Checking for open issues..."

  # Build jq priority sorter from configured prefixes.
  # Priority label detection is by prefix match (e.g. P0-critical, P1-high).
  # Unlabelled falls last.
  # Skip issues in SKIP_ISSUE_NUMBERS.
  ISSUE=$(gh issue list --state open --json number,title,labels --jq '
    . as $all
    | $all
    | map(select(.number != 0))
    | .[]' 2>/dev/null | head -n 1 >/dev/null || true)

  if [ "$CLAUDE_RATE_LIMITED" = true ]; then
    # When Claude is rate limited, only consider P3 issues (best effort).
    ISSUES=$(gh issue list --state open --json number,title,labels --jq '
      [.[]] |
      map(select(.number != 0)) |
      map(select(.labels | any(.name | startswith("P3")))) |
      sort_by(.number)
    ' 2>>"$LOG_FILE" || true)
  else
    # Normal: P0 > P1 > P2 > P3 > other; then oldest (lowest number).
    ISSUES=$(gh issue list --state open --json number,title,labels --jq '
      [.[]] |
      map(select(.number != 0)) |
      def priority:
        [.labels[]?.name // empty]
        | if any(startswith("P0")) then 0
          elif any(startswith("P1")) then 1
          elif any(startswith("P2")) then 2
          elif any(startswith("P3")) then 3
          else 4 end;
      sort_by([priority, .number])
    ' 2>>"$LOG_FILE" || true)
  fi

  ISSUE="$(pick_first_eligible_issue "$ISSUES")"
  if [ -z "$ISSUE" ]; then
    log "No eligible open issues found. Done."
    exit 0
  fi

  NUMBER=$(echo "$ISSUE" | jq -r '.number')
  TITLE=$(echo "$ISSUE" | jq -r '.title')

  BODY=$(gh issue view "$NUMBER" --json body --jq '.body' 2>/dev/null || echo "")
  BRANCH="${BRANCH_PREFIX}${NUMBER}"

  log "Working on issue #${NUMBER}: ${TITLE} (base=${DEFAULT_BRANCH})"

  EXISTING_PR=$(gh pr list --search "issue-${NUMBER}" --json number --jq '.[0].number // empty' 2>/dev/null || true)
  if [ -n "$EXISTING_PR" ]; then
    log "SKIP: PR #${EXISTING_PR} already exists for issue #${NUMBER}"
    exit 0
  fi

  if git rev-parse --verify "$BRANCH" >/dev/null 2>&1; then
    git checkout "$BRANCH"
  else
    git checkout -b "$BRANCH"
  fi

  jq -n \
    --arg number "$NUMBER" \
    --arg title "$TITLE" \
    --arg body "$BODY" \
    --arg branch "$BRANCH" \
    --arg status "in_progress" \
    '{number: $number, title: $title, body: $body, branch: $branch, status: $status}' \
    > "$STATE_FILE"
else
  # Ensure branch exists and is checked out.
  git checkout "$BRANCH" 2>>"$LOG_FILE" || true
fi

# Optional roadmap context (repo-local)
ROADMAP=""
if [ -n "$ROADMAP_ISSUE_NUMBER" ]; then
  ROADMAP=$(gh issue view "$ROADMAP_ISSUE_NUMBER" --json body --jq '.body' 2>/dev/null || echo "")
fi

RESUME_CONTEXT=""
if [ "$RESUMING" = true ]; then
  CHANGES=$(git diff --stat HEAD 2>/dev/null || true)
  COMMITTED=$(git log "${DEFAULT_BRANCH}"..HEAD --oneline 2>/dev/null || true)
  RESUME_CONTEXT="
IMPORTANT: This is a RESUMED session. A previous run was interrupted.

Progress so far on this branch:
Commits since ${DEFAULT_BRANCH}:
${COMMITTED:-None yet}

Uncommitted changes:
${CHANGES:-None}
"
fi

# ── Run the agent CLI (Claude/Gemini, with Ollama fallback) ─────
AGENT_PROMPT="
You are an autonomous coding agent working in the repo at: ${REPO_DIR}

${RESUME_CONTEXT}

REFERENCE (optional):
${ROADMAP}

Your task is to implement a solution for this GitHub issue:

Issue #${NUMBER}: ${TITLE}

${BODY}

Process:
1. PLAN/ANALYZE
2. IMPLEMENT
3. TEST (if applicable)
4. COMMIT with:
   fix: <short description>

   Closes #${NUMBER}
"

USED_PROVIDER=""

if [ "$PREFER_CLAUDE" = "1" ] && [ "$CLAUDE_RATE_LIMITED" = false ]; then
  log "Running Claude Code on issue #${NUMBER}..."
  USED_PROVIDER="claude"
  if ! claude -p --verbose --model opus "$AGENT_PROMPT" --allowedTools Bash,Read,Write,Edit,MultiEdit 2>&1 | tee -a "$LOG_FILE"; then
    # If Claude fails, fall back to Gemini.
    log "WARN: Claude failed; falling back to Gemini."
    USED_PROVIDER=""
  fi
fi

if [ -z "$USED_PROVIDER" ]; then
  log "Using Gemini for issue #${NUMBER}..."
  USED_PROVIDER="gemini"
  if ! command -v gemini >/dev/null 2>&1; then
    log "Installing Gemini CLI via npm..."
    npm install -g @google/gemini-cli 2>&1 | tee -a "$LOG_FILE" || true
  fi
  _tmp="$(mktemp)"
  set +e
  gemini --yolo -p "$AGENT_PROMPT" --output-format json 2>&1 | tee -a "$LOG_FILE" | tee "$_tmp" >/dev/null
  gem_rc="${PIPESTATUS[0]}"
  set -e
  if [ "$gem_rc" -ne 0 ] && grep -qiE "Please set an Auth method|GEMINI_API_KEY|GOOGLE_GENAI_USE_VERTEXAI|GOOGLE_GENAI_USE_GCA|RESOURCE_EXHAUSTED|credits are depleted|prepayment credits are depleted|rate limit|429|too many requests|quota" "$_tmp"; then
    log "GEMINI: auth/billing/rate-limit detected. Falling back to Ollama."
    if [ "$OLLAMA_P3_ONLY" = "1" ] && ! is_p3_issue_number "$NUMBER"; then
      P3_NUM="$(pick_first_p3_issue_number)"
      if [ -z "${P3_NUM:-}" ]; then
        create_p3_issue_from_repo_scan
        log "OLLAMA: no P3 issue available; exiting."
        exit 0
      fi
      log "OLLAMA: switching from #${NUMBER} to P3 issue #${P3_NUM}."
      NUMBER="$P3_NUM"
      TITLE="$(gh issue view "$NUMBER" --json title --jq '.title' 2>/dev/null || echo "P3 issue #${NUMBER}")"
      BODY="$(gh issue view "$NUMBER" --json body --jq '.body' 2>/dev/null || echo "")"
      BRANCH="${BRANCH_PREFIX}${NUMBER}"
      git checkout "$DEFAULT_BRANCH" 2>>"$LOG_FILE" || true
      git pull origin "$DEFAULT_BRANCH" 2>>"$LOG_FILE" || true
      if git rev-parse --verify "$BRANCH" >/dev/null 2>&1; then
        git checkout "$BRANCH"
      else
        git checkout -b "$BRANCH"
      fi
      jq -n \
        --arg number "$NUMBER" \
        --arg title "$TITLE" \
        --arg body "$BODY" \
        --arg branch "$BRANCH" \
        --arg status "in_progress" \
        '{number: $number, title: $title, body: $body, branch: $branch, status: $status}' \
        > "$STATE_FILE"
      # Rebuild prompt for new issue.
      AGENT_PROMPT="
You are an autonomous coding agent working in the repo at: ${REPO_DIR}

REFERENCE (optional):
${ROADMAP}

Your task is to implement a solution for this GitHub issue:

Issue #${NUMBER}: ${TITLE}

${BODY}

Process:
1. PLAN/ANALYZE
2. IMPLEMENT
3. TEST (if applicable)
4. COMMIT with:
   fix: <short description>

   Closes #${NUMBER}
"
    fi
    run_ollama_agent "$AGENT_PROMPT" || log "OLLAMA: fallback failed."
    USED_PROVIDER="ollama"
  elif [ "$gem_rc" -ne 0 ]; then
    log "WARN: Gemini exited non-zero (rc=${gem_rc}). Not treating as fallback; check logs."
  fi
  rm -f "$_tmp" 2>/dev/null || true
fi

# ── Post-agent: commit (if needed) ──────────────────────────────
HAS_CHANGES=false
ACTUAL_CHANGES=$(git status --porcelain | grep -v "\.DS_Store" || true)
if [ -n "$ACTUAL_CHANGES" ]; then HAS_CHANGES=true; fi
if [ -n "$(git log "${DEFAULT_BRANCH}"..HEAD --oneline 2>/dev/null)" ]; then HAS_CHANGES=true; fi

if [ "$HAS_CHANGES" = false ]; then
  log "ERROR: Agent made no changes. Cleaning up."
  git checkout "$DEFAULT_BRANCH"
  git branch -D "$BRANCH" 2>/dev/null || true
  rm -f "$STATE_FILE"
  exit 1
fi

if [ -n "$(git status --porcelain)" ]; then
  git add -A
  git commit -m "$(cat <<EOF
fix: implement solution for issue #${NUMBER}

Closes #${NUMBER}

Automated implementation by auto-worker.
EOF
)" 2>/dev/null || true
fi

: "${GH_TOKEN:?GH_TOKEN is required for non-interactive push/PR create}"

if ! git -c "http.https://github.com/.extraheader=Authorization: basic $(echo -n "x-access-token:${GH_TOKEN}" | base64)" push -u origin "$BRANCH" 2>&1 | tee -a "$LOG_FILE"; then
  log "ERROR: git push failed (branch ${BRANCH}). State file kept for resume."
  exit 1
fi

if ! gh pr create \
  --title "fix: ${TITLE}" \
  --body "$(cat <<EOF
## Summary

Automated implementation for #${NUMBER}.

## Issue

Closes #${NUMBER}

## Review Checklist

- [ ] Code changes match the issue requirements
- [ ] No unrelated files were modified
- [ ] Tests pass
- [ ] Code follows existing project patterns

---
*This PR was generated automatically by the auto-worker.*
EOF
)" 2>&1 | tee -a "$LOG_FILE"; then
  log "ERROR: gh pr create failed (branch ${BRANCH} was pushed). Open PR manually; state not cleared."
  exit 1
fi

rm -f "$STATE_FILE"
git checkout "$DEFAULT_BRANCH"
log "Done with issue #${NUMBER}. PR created."

