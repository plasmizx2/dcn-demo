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
SECRETS_FILE="${SECRETS_FILE:-$HOME/.auto-worker/secrets.json}"
SECRETS_PROJECT="${SECRETS_PROJECT:-dcn-demo}"
HEARTBEAT_INTERVAL_SECONDS="${HEARTBEAT_INTERVAL_SECONDS:-30}"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG_FILE"; }

ensure_gh_token() {
  # Prefer explicit GH_TOKEN, but fall back to `gh auth token` for interactive environments.
  if [ -n "${GH_TOKEN:-}" ]; then
    return 0
  fi
  if command -v gh >/dev/null 2>&1; then
    GH_TOKEN="$(gh auth token 2>/dev/null || true)"
    export GH_TOKEN
  fi
  return 0
}

detect_claude_rate_limit_now() {
  # Fast probe so Claude rate limiting doesn't delay Gemini.
  # Returns 0 if rate-limited, 1 otherwise.
  if ! command -v claude >/dev/null 2>&1; then
    return 1
  fi
  python3 - <<'PY'
import subprocess, sys
try:
    p = subprocess.run(
        ["claude", "-p", "--model", "opus", "Respond with OK only."],
        input=b"",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=8,
        check=False,
    )
    out = (p.stdout or b"").decode("utf-8", "ignore").lower()
    if "you've hit your limit" in out or "hit your limit" in out or "rate limit" in out:
        sys.exit(0)
    sys.exit(1)
except subprocess.TimeoutExpired:
    # Treat timeouts as "not confirmed rate limit" (don't block Gemini).
    sys.exit(1)
except Exception:
    sys.exit(1)
PY
}

issue_comment_already_implemented() {
  # $1: issue number
  # $2: optional short reason
  local n="$1"
  local reason="${2:-}"
  [ -z "$n" ] && return 0
  gh issue comment "$n" --body "$(cat <<EOF
## Auto-worker note

I attempted to work this issue but it appears the requested behavior may already be implemented (or there wasn't a clear code change to make).

${reason:+**Reason observed:** ${reason}}

### What you can do next
- If this issue is truly done: **close it**.
- If it still isn't done: please **expand the issue** with concrete acceptance criteria (what screen/API, exact expected behavior, and how to verify), and mention what's currently broken/missing.

EOF
)" 2>>"$LOG_FILE" || true
}

get_repo_full_name() {
  gh repo view --json nameWithOwner --jq '.nameWithOwner' 2>/dev/null || true
}

fetch_pr_feedback() {
  # $1: PR number
  # Outputs a short markdown-ish summary of the most recent PR feedback.
  local pr_number="$1"
  [ -z "$pr_number" ] && return 0
  local repo
  repo="$(get_repo_full_name)"
  [ -z "$repo" ] && return 0

  {
    echo "PR #${pr_number} feedback (most recent first):"
    echo ""

    # Issue comments on the PR (general discussion)
    gh api "repos/${repo}/issues/${pr_number}/comments" --jq '
      sort_by(.created_at) | reverse | .[:20] |
      .[] | "- [issue-comment] " + (.user.login // "unknown") + " (" + (.created_at // "") + "):\n  " + ((.body // "") | gsub("\\r";"") | gsub("\\n";"\n  "))
    ' 2>/dev/null || true

    # Review comments (inline on diffs)
    gh api "repos/${repo}/pulls/${pr_number}/comments" --jq '
      sort_by(.created_at) | reverse | .[:30] |
      .[] | "- [review-comment] " + (.user.login // "unknown") + " (" + (.created_at // "") + ") " +
            (if .path then ("[" + .path + (if .line then (":" + (.line|tostring)) else "" end) + "] ") else "" end) +
            ":\n  " + ((.body // "") | gsub("\\r";"") | gsub("\\n";"\n  "))
    ' 2>/dev/null || true
  } | sed '/^[[:space:]]*$/N;/^\n$/D' || true
}

post_pr_reply() {
  # $1: PR number
  # $2: body
  local pr_number="$1"
  local body="$2"
  [ -z "$pr_number" ] && return 0
  [ -z "$body" ] && return 0
  gh pr comment "$pr_number" --body "$body" 2>>"$LOG_FILE" || true
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "auto-worker-core requires '$1' on PATH" >&2
    exit 1
  }
}

run_gemini_model_ladder() {
  # $1: prompt text
  # Falls back to next model if we get 503 "high demand"/UNAVAILABLE.
  local prompt="$1"
  local models=("gemini-2.5-pro" "gemini-2.5-flash" "gemini-2.5-flash-lite")
  local m tmp rc

  tmp="$(mktemp)"
  for m in "${models[@]}"; do
    log "GEMINI: trying model=${m}"
    : >"$tmp"
    set +e
    gemini -m "$m" -p "$prompt" --output-format text 2>&1 | tee -a "$LOG_FILE" | tee "$tmp" >/dev/null
    rc="${PIPESTATUS[0]}"
    set -e

    if [ "$rc" -eq 0 ]; then
      rm -f "$tmp" 2>/dev/null || true
      return 0
    fi

    # Try next model on 503/high demand.
    if grep -qiE "\"code\"\s*:\s*503|\b503\b|high demand|UNAVAILABLE" "$tmp"; then
      log "GEMINI: model ${m} overloaded/unavailable (503). Falling back..."
      continue
    fi

    # Non-503 error: stop and let caller handle.
    rm -f "$tmp" 2>/dev/null || true
    return "$rc"
  done

  rm -f "$tmp" 2>/dev/null || true
  return 503
}

extract_first_unified_diff() {
  # Reads stdin, outputs first unified diff to stdout (best-effort).
  # NOTE: uses python3 -c (not heredoc) so piped stdin is available for data.
  python3 -c '
import re, sys
s = sys.stdin.read()
s = s.lstrip("\ufeff\u200b\u200c\u200d")
m = re.search(r"```diff\s*(.*?)\s*```", s, re.S|re.I)
if m:
  sys.stdout.write(m.group(1).strip() + "\n")
  raise SystemExit(0)
m = re.search(r"(?s)\bdiff --git\b.*", s)
if m:
  out = m.group(0).lstrip()
  sys.stdout.write(out)
  if not out.endswith("\n"):
    sys.stdout.write("\n")
  raise SystemExit(0)
m = re.search(r"(?ms)^(---\s+a/.*?\n\+\+\+\s+b/.*)$", s)
if m:
  sys.stdout.write(m.group(1))
  if not m.group(1).endswith("\n"):
    sys.stdout.write("\n")
  raise SystemExit(0)
raise SystemExit(1)
'
}

run_gemini_patch_ladder_and_apply() {
  # $1: issue number, $2: title, $3: body
  local n="$1"
  local title="$2"
  local body="$3"

  if ! command -v gemini >/dev/null 2>&1; then
    log "Installing Gemini CLI via npm..."
    npm install -g @google/gemini-cli 2>&1 | tee -a "$LOG_FILE" || true
  fi
  require_cmd gemini

  if [ -z "${GEMINI_API_KEY:-}" ]; then
    log "ERROR: GEMINI_API_KEY is not set."
    return 41
  fi

  local prompt
  prompt="$(cat <<EOF
You are a coding agent operating in a git repo.

CRITICAL OUTPUT RULES:
- Output MUST be ONLY a single unified diff that can be applied with: git apply
- Do NOT wrap in code fences.
- Do NOT include any explanation text.
- Prefer starting with: diff --git
- If you cannot comply, output nothing.

Repo context: ${REPO_DIR}

Fix GitHub issue #${n}: ${title}

Requirements context (issue + latest PR feedback):
${body}
EOF
)"

  local models=("gemini-2.5-pro" "gemini-2.5-flash" "gemini-2.5-flash-lite")
  local m tmp_out tmp_diff rc
  tmp_out="$(mktemp)"
  tmp_diff="$(mktemp)"

  for m in "${models[@]}"; do
    log "GEMINI: patch mode model=${m}"
    : >"$tmp_out"
    set +e
    gemini -m "$m" -p "$prompt" --output-format text >"$tmp_out" 2>&1
    rc=$?
    set -e

    if [ "$rc" -ne 0 ] && grep -qiE "\b503\b|high demand|UNAVAILABLE" "$tmp_out"; then
      log "GEMINI: patch mode ${m} overloaded/unavailable (503). Falling back..."
      continue
    fi

    # Even if Gemini exits non-zero, it sometimes still prints a diff.
    # Attempt to extract+apply regardless; only treat as hard-failure if no diff or apply fails.
    if ! extract_first_unified_diff <"$tmp_out" >"$tmp_diff"; then
      log "GEMINI: patch mode did not output an applyable diff."
      cat "$tmp_out" >>"$LOG_FILE"
      if [ "$rc" -ne 0 ]; then
        rm -f "$tmp_out" "$tmp_diff" 2>/dev/null || true
        return "$rc"
      fi
      rm -f "$tmp_out" "$tmp_diff" 2>/dev/null || true
      return 1
    fi

    if git apply --3way "$tmp_diff" 2>>"$LOG_FILE"; then
      log "GEMINI: patch applied successfully."
      rm -f "$tmp_out" "$tmp_diff" 2>/dev/null || true
      return 0
    fi

    log "GEMINI: patch failed to apply."
    cat "$tmp_out" >>"$LOG_FILE"
    rm -f "$tmp_out" "$tmp_diff" 2>/dev/null || true
    return 1
  done

  rm -f "$tmp_out" "$tmp_diff" 2>/dev/null || true
  return 503
}

pick_ollama_model() {
  if [ -n "$OLLAMA_MODEL" ]; then
    echo "$OLLAMA_MODEL"
    return 0
  fi
  if ! command -v ollama >/dev/null 2>&1; then
    echo ""
    return 0
  fi
  local out
  out="$(ollama list 2>&1 || true)"
  if echo "$out" | grep -qiE "could not connect|connection refused|dial tcp|failed to connect"; then
    echo ""
    return 0
  fi
  local names
  names="$(printf "%s\n" "$out" | awk 'NR>1 {print $1}' || true)"
  if echo "$names" | grep -qx "qwen2.5:7b"; then echo "qwen2.5:7b"; return 0; fi
  if echo "$names" | grep -qx "qwen2.5:3b"; then echo "qwen2.5:3b"; return 0; fi
  echo "$names" | head -n 1
}

run_ollama_agent() {
  local prompt="$1"
  if [ "$OLLAMA_FALLBACK_ENABLED" != "1" ]; then
    log "OLLAMA: fallback disabled (OLLAMA_FALLBACK_ENABLED=${OLLAMA_FALLBACK_ENABLED})"
    return 1
  fi
  if ! command -v ollama >/dev/null 2>&1; then
    log "OLLAMA: not installed/on PATH"
    return 1
  fi
  if ! ollama list >/dev/null 2>&1; then
    if [ "${DRY_RUN:-0}" = "1" ]; then
      log "OLLAMA: server not reachable; DRY_RUN so not starting server."
    else
      log "OLLAMA: server not reachable; starting 'ollama serve' in background..."
      (nohup ollama serve >/dev/null 2>&1 &)
      sleep 1
    fi
  fi
  local model
  model="$(pick_ollama_model)"
  if [ -z "$model" ]; then
    log "OLLAMA: no installed models found OR server unreachable."
    return 1
  fi
  log "OLLAMA: running model=${model}"
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
  # NOTE: `gh ... --jq` does not support passing jq args; interpolate safely via Python.
  local pfx_escaped
  pfx_escaped="$(printf "%s" "$BRANCH_PREFIX" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))')"
  gh pr list --state open --author "@me" --json headRefName,number,title --jq \
    "[.[] | select(.headRefName | startswith(${pfx_escaped}))] | .[0] // empty" 2>/dev/null || true
}

infer_issue_number_from_branch() {
  local b="${1:-}"
  python3 -c '
import re, sys
b = sys.argv[1] if len(sys.argv) > 1 else ""
m = re.search(r"issue-([0-9]+)", b)
print(m.group(1) if m else "")
' "$b"
}

infer_issue_number_from_pr() {
  local prn="${1:-}"
  [ -z "$prn" ] && return 0
  local body
  body="$(gh pr view "$prn" --json body --jq '.body // ""' 2>/dev/null || true)"
  python3 -c '
import re, sys
s = sys.argv[1] if len(sys.argv) > 1 else ""
m = re.search(r"(?i)closes\s*#(\d+)", s)
if not m:
  m = re.search(r"#(\d+)", s)
print(m.group(1) if m else "")
' "$body"
}

# ── Startup ─────────────────────────────────────────────────────
ensure_log_dir
cd "$REPO_DIR" || { echo "REPO_DIR not found: $REPO_DIR" >&2; exit 1; }
for c in jq gh git; do require_cmd "$c"; done

# Cron/monitor-safe Gemini auth: load GEMINI_API_KEY from ~/.auto-worker/secrets.json if missing.
if [ -z "${GEMINI_API_KEY:-}" ] && [ -f "$SECRETS_FILE" ] && command -v jq >/dev/null 2>&1; then
  GEMINI_API_KEY="$(jq -r --arg p "$SECRETS_PROJECT" '.gemini_api_keys[$p] // empty' "$SECRETS_FILE" 2>/dev/null || true)"
  export GEMINI_API_KEY
fi

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
STOP_REQUESTED=0

cleanup() {
  rm -f "$LOCK_FILE" 2>/dev/null || true
  if [ -n "${HEARTBEAT_PID:-}" ]; then
    kill "$HEARTBEAT_PID" 2>/dev/null || true
  fi
  if [ "${DID_STASH:-0}" = "1" ]; then
    if [ -z "$(git status --porcelain 2>/dev/null || true)" ]; then
      git stash pop -q 2>>"$LOG_FILE" || true
      log "GIT: restored pre-run stash."
    else
      log "GIT: leaving pre-run stash (working tree not clean)."
    fi
  fi
}

save_progress_and_exit() {
  STOP_REQUESTED=1
  log "STOP: received stop signal; saving progress..."
  local n=""
  local branch=""
  if [ -f "$STATE_FILE" ]; then
    n="$(jq -r '.number // empty' "$STATE_FILE" 2>/dev/null || true)"
    branch="$(jq -r '.branch // empty' "$STATE_FILE" 2>/dev/null || true)"
  fi
  if [ -n "$(git status --porcelain 2>/dev/null || true)" ]; then
    git add -A 2>>"$LOG_FILE" || true
    git commit -m "wip: partial progress on issue #${n:-unknown} (stopped)

Work in progress — stopped from monitor. Resume later." 2>>"$LOG_FILE" || true
    log "STOP: saved WIP commit (issue #${n:-unknown}, branch ${branch:-unknown})."
  else
    log "STOP: no uncommitted changes to save."
  fi
  exit 0
}

trap cleanup EXIT
trap save_progress_and_exit TERM INT

log "START: repo=${REPO_DIR}, dry_run=${DRY_RUN}, state_file=${STATE_FILE}"

ensure_gh_token

# Periodic heartbeat so logs show we're alive.
HEARTBEAT_PID=""
if [ "${HEARTBEAT_INTERVAL_SECONDS:-0}" -gt 0 ] 2>/dev/null; then
  (
    while true; do
      sleep "$HEARTBEAT_INTERVAL_SECONDS" || exit 0
      echo "[$(date '+%Y-%m-%d %H:%M:%S')] HEARTBEAT: alive (pid $$)" >> "$LOG_FILE"
    done
  ) &
  HEARTBEAT_PID="$!"
  log "HEARTBEAT: enabled (every ${HEARTBEAT_INTERVAL_SECONDS}s, pid ${HEARTBEAT_PID})"
fi

# Always stash local changes so branch checkouts/pulls can't fail.
DID_STASH=0
if [ -n "$(git status --porcelain 2>/dev/null || true)" ]; then
  log "GIT: working tree dirty; creating temporary stash for auto-worker."
  git stash push -u -m "auto-worker temp stash $(date '+%Y-%m-%d %H:%M:%S')" 2>>"$LOG_FILE" || true
  DID_STASH=1
fi

# DRY_RUN=1: compute what would be done and log it, without any mutations.
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

# Also probe live so we don't waste time attempting Claude.
if [ "$CLAUDE_RATE_LIMITED" = false ] && detect_claude_rate_limit_now; then
  CLAUDE_RATE_LIMITED=true
  log "Claude is rate limited (live probe). Skipping Claude and going straight to Gemini."
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
  # If there's an open auto-worker PR, automatically resume it (no manual state needed).
  OPEN_AUTO_PR=$(has_open_autoworker_pr)
  if [ -n "$OPEN_AUTO_PR" ]; then
    OPEN_PR_NUM=$(echo "$OPEN_AUTO_PR" | jq -r '.number')
    OPEN_PR_TITLE=$(echo "$OPEN_AUTO_PR" | jq -r '.title')
    OPEN_PR_BRANCH=$(echo "$OPEN_AUTO_PR" | jq -r '.headRefName')

    INFERRED_NUM="$(infer_issue_number_from_branch "$OPEN_PR_BRANCH")"
    if [ -z "$INFERRED_NUM" ]; then
      INFERRED_NUM="$(infer_issue_number_from_pr "$OPEN_PR_NUM")"
    fi
    if [ -n "$INFERRED_NUM" ]; then
      NUMBER="$INFERRED_NUM"
      BRANCH="$OPEN_PR_BRANCH"
      TITLE="$(gh issue view "$NUMBER" --json title --jq '.title' 2>/dev/null || echo "$OPEN_PR_TITLE")"
      BODY="$(gh issue view "$NUMBER" --json body --jq '.body' 2>/dev/null || echo "")"
      RESUMING=true

      jq -n \
        --arg number "$NUMBER" \
        --arg title "$TITLE" \
        --arg body "$BODY" \
        --arg branch "$BRANCH" \
        --arg status "in_progress" \
        '{number: $number, title: $title, body: $body, branch: $branch, status: $status}' \
        > "$STATE_FILE"

      log "AUTO-RESUME: Found open PR #${OPEN_PR_NUM} (${OPEN_PR_TITLE}); resuming issue #${NUMBER} on branch ${BRANCH}"
    else
      log "WAIT: PR #${OPEN_PR_NUM} (${OPEN_PR_TITLE}) is still open. Merge or close it before I start the next issue."
      exit 0
    fi
  fi

  # If we auto-resumed, skip picking a new issue.
  if [ "$RESUMING" = true ]; then
    log "AUTO-RESUME: skipping issue queue (continuing on branch ${BRANCH})"
  else
    log "Checking for open issues..."

    # Normal priority sort: P0 > P1 > P2 > P3 > other; then oldest (lowest number).
    # Claude rate-limit only affects which AI model is used, not which issues we pick.
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
      log "No eligible open issues found. Done."
      exit 0
    fi

    NUMBER=$(echo "$ISSUE" | jq -r '.number')
    TITLE=$(echo "$ISSUE" | jq -r '.title')

    BODY=$(gh issue view "$NUMBER" --json body --jq '.body' 2>/dev/null || echo "")
    BRANCH="${BRANCH_PREFIX}${NUMBER}"

    log "Working on issue #${NUMBER}: ${TITLE} (base=${DEFAULT_BRANCH})"

    # Only block if there's an OPEN PR for this issue. Closed PRs should not prevent rework.
    EXISTING_PR=$(gh pr list --state open --search "issue-${NUMBER}" --json number --jq '.[0].number // empty' 2>/dev/null || true)
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
  fi
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

# ── Fetch PR feedback and inject into prompt ─────────────────────
PR_FEEDBACK=""
OPEN_HEAD_PR_NUM="$(gh pr list --state open --head "$BRANCH" --json number --jq '.[0].number // empty' 2>/dev/null || true)"
if [ -n "${OPEN_HEAD_PR_NUM:-}" ]; then
  PR_FEEDBACK="$(fetch_pr_feedback "$OPEN_HEAD_PR_NUM" || true)"
  log "PR CONTEXT: loaded feedback from PR #${OPEN_HEAD_PR_NUM} ($(printf "%s" "$PR_FEEDBACK" | wc -c | tr -d ' ') bytes)"
  if [ "${STOP_AFTER_PR_FEEDBACK:-0}" = "1" ]; then
    log "WARNING: STOP_AFTER_PR_FEEDBACK=1 is set — this debug flag prevents actual work. Unset it to allow full runs."
    log "STOP_AFTER_PR_FEEDBACK=1 set; exiting after loading PR context."
    exit 0
  fi
fi

if [ -n "${PR_FEEDBACK:-}" ]; then
  BODY="$(cat <<EOF
${BODY}

--- PR feedback ---
${PR_FEEDBACK}
EOF
)"
fi

AGENT_PROMPT="
You are an autonomous coding agent working in the repo at: ${REPO_DIR}

${RESUME_CONTEXT}

PR CONTEXT (if any):
${PR_FEEDBACK}

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
  run_gemini_patch_ladder_and_apply "$NUMBER" "$TITLE" "$BODY" 2>&1 | tee -a "$LOG_FILE" | tee "$_tmp" >/dev/null
  gem_rc="${PIPESTATUS[0]}"
  set -e
  if [ "$gem_rc" -ne 0 ] && grep -qiE "Please set an Auth method|GEMINI_API_KEY|GOOGLE_GENAI_USE_VERTEXAI|RESOURCE_EXHAUSTED|credits are depleted|rate limit|429|too many requests|quota" "$_tmp"; then
    log "GEMINI: auth/billing/rate-limit detected. Falling back to Ollama."
    run_ollama_agent "$AGENT_PROMPT" || log "OLLAMA: fallback failed."
    USED_PROVIDER="ollama"
  elif [ "$gem_rc" -eq 503 ] || grep -qiE "\"code\"\s*:\s*503|\b503\b|high demand|UNAVAILABLE" "$_tmp"; then
    log "ERROR: Gemini models are overloaded/unavailable (503). Continuing to post-agent step."
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
  reason=""
  if tail -200 "$LOG_FILE" 2>/dev/null | grep -qiE "already implemented|task complete|consider this task complete|feature is implemented|nothing to do"; then
    reason="Agent output indicates it may already be implemented."
    issue_comment_already_implemented "$NUMBER" "$reason"
  fi
  log "ERROR: Agent made no changes. Cleaning up."
  git checkout "$DEFAULT_BRANCH"
  git branch -D "$BRANCH" 2>/dev/null || true
  rm -f "$STATE_FILE"
  exit 1
fi

# Record the SHA before we commit/push so we can detect truly new commits.
SHA_BEFORE_COMMIT="$(git rev-parse HEAD 2>/dev/null || echo "")"

if [ -n "$(git status --porcelain)" ]; then
  # Selectively stage changes — explicitly exclude auto-worker tooling files
  # that may appear modified in the working tree (they are local-only and must
  # not be committed to feature branches).
  git add -A
  git reset HEAD -- auto-worker-core.sh auto-worker.sh auto-worker-uninstall.sh auto-worker-monitor/ .gitignore 2>/dev/null || true
  # Only commit if there are staged changes after excluding tooling files.
  if [ -n "$(git diff --cached --name-only)" ]; then
    git commit -m "fix: implement solution for issue #${NUMBER}

Closes #${NUMBER}

Automated implementation by auto-worker." 2>/dev/null || true
  else
    log "INFO: Only tooling files changed (no real code changes to commit)."
  fi
fi

ensure_gh_token
: "${GH_TOKEN:?GH_TOKEN is required for non-interactive push/PR create (or run: gh auth login)}"

if ! git -c "http.https://github.com/.extraheader=Authorization: basic $(echo -n "x-access-token:${GH_TOKEN}" | base64)" push -u origin "$BRANCH" 2>&1 | tee -a "$LOG_FILE"; then
  log "ERROR: git push failed (branch ${BRANCH}). State file kept for resume."
  exit 1
fi

# ── Post a PR comment ONLY when a genuinely new commit was pushed ──
SHA_AFTER_COMMIT="$(git rev-parse HEAD 2>/dev/null || echo "")"
PUSH_PR_NUM="$(gh pr list --state open --head "$BRANCH" --json number --jq '.[0].number // empty' 2>/dev/null || true)"

if [ -n "${PUSH_PR_NUM:-}" ] && [ "$SHA_AFTER_COMMIT" != "$SHA_BEFORE_COMMIT" ]; then
  PUSH_COMMIT_SHA="$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")"
  PUSH_COMMIT_MSG="$(git log -1 --pretty=%s 2>/dev/null || echo "")"
  PUSH_FILES_CHANGED="$(git diff --name-only HEAD~1..HEAD 2>/dev/null | head -20 || echo "(unknown)")"
  _pr_body="## Auto-worker update

Commit: ${PUSH_COMMIT_SHA} -- ${PUSH_COMMIT_MSG}
Provider: ${USED_PROVIDER}

Files changed:
${PUSH_FILES_CHANGED}

---
Pushed by auto-worker. Leave a comment to request changes."
  post_pr_reply "$PUSH_PR_NUM" "$_pr_body"
  log "PR COMMENT: posted update on PR #${PUSH_PR_NUM} (commit ${PUSH_COMMIT_SHA})"
elif [ -n "${PUSH_PR_NUM:-}" ]; then
  log "PR COMMENT: skipped -- no new commit was made (nothing to report on PR #${PUSH_PR_NUM})"
fi

# ── Create or skip PR ─────────────────────────────────────────────
EXISTING_HEAD_PR="$(gh pr list --state open --head "$BRANCH" --json number --jq '.[0].number // empty' 2>/dev/null || true)"
if [ -n "${EXISTING_HEAD_PR:-}" ]; then
  log "INFO: PR #${EXISTING_HEAD_PR} already exists for branch ${BRANCH}; skipping gh pr create."
  rm -f "$STATE_FILE"
  git checkout "$DEFAULT_BRANCH"
  if [ "$RESUMING" = true ]; then
    log "WAITING FOR REVIEW: Responded to feedback on PR #${EXISTING_HEAD_PR} for issue #${NUMBER}. Waiting for review."
  else
    log "Done with issue #${NUMBER}. PR updated."
  fi
  exit 0
fi

if ! gh pr create \
  --title "fix: ${TITLE}" \
  --body "## Summary

Automated implementation for #${NUMBER}.

## Issue

Closes #${NUMBER}

## Review Checklist

- [ ] Code changes match the issue requirements
- [ ] No unrelated files were modified
- [ ] Tests pass
- [ ] Code follows existing project patterns

---
This PR was generated automatically by the auto-worker." 2>&1 | tee -a "$LOG_FILE"; then
  if tail -200 "$LOG_FILE" | grep -qiE "pull request.*already exists|a pull request for branch .* already exists"; then
    log "INFO: PR already exists for branch ${BRANCH}; continuing."
  else
    log "ERROR: gh pr create failed (branch ${BRANCH} was pushed). State not cleared."
    exit 1
  fi
fi

rm -f "$STATE_FILE"
git checkout "$DEFAULT_BRANCH"
log "Done with issue #${NUMBER}. PR created."
