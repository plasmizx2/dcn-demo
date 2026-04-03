#!/bin/bash
# DCN Auto Issue Worker
# Runs via cron every hour — picks the oldest open issue, uses Claude Code CLI
# to plan + implement a fix, then opens a PR for review.
# If rate-limited mid-run, saves progress and resumes next time.

set -euo pipefail

export PATH="/opt/homebrew/bin:/opt/homebrew/sbin:/Users/seandumont/.pyenv/shims:/Users/seandumont/.pyenv/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
export NODE_TLS_REJECT_UNAUTHORIZED=0

REPO_DIR="/Users/seandumont/Desktop/dcn-demo"
LOG_FILE="/Users/seandumont/Desktop/dcn-demo/auto-worker.log"
LOCK_FILE="/tmp/dcn-auto-worker.lock"
STATE_FILE="/Users/seandumont/Desktop/dcn-demo/.auto-worker-state.json"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG_FILE"; }

# Prevent overlapping runs
if [ -f "$LOCK_FILE" ]; then
  LOCK_PID=$(cat "$LOCK_FILE" 2>/dev/null)
  if kill -0 "$LOCK_PID" 2>/dev/null; then
    log "SKIP: previous run (PID $LOCK_PID) still active"
    exit 0
  fi
  rm -f "$LOCK_FILE"
fi
echo $$ > "$LOCK_FILE"
trap 'rm -f "$LOCK_FILE"' EXIT

cd "$REPO_DIR"

# ── Check for interrupted work from a previous run ──────────────
RESUMING=false
if [ -f "$STATE_FILE" ]; then
  SAVED_NUMBER=$(jq -r '.number' "$STATE_FILE")
  SAVED_BRANCH=$(jq -r '.branch' "$STATE_FILE")
  SAVED_STATUS=$(jq -r '.status' "$STATE_FILE")

  if [ "$SAVED_STATUS" = "in_progress" ]; then
    log "RESUME: Found interrupted work on issue #${SAVED_NUMBER} (branch ${SAVED_BRANCH})"
    RESUMING=true
    NUMBER="$SAVED_NUMBER"
    TITLE=$(jq -r '.title' "$STATE_FILE")
    BODY=$(jq -r '.body' "$STATE_FILE")
    BRANCH="$SAVED_BRANCH"

    # Make sure we're on the right branch
    git checkout "$BRANCH" 2>/dev/null || {
      log "ERROR: Could not checkout branch ${SAVED_BRANCH}. Starting fresh."
      RESUMING=false
      rm -f "$STATE_FILE"
    }

    if [ "$RESUMING" = true ]; then
      git pull origin master --no-edit 2>/dev/null || true
    fi
  fi
fi

# ── If not resuming, pick a new issue ───────────────────────────
if [ "$RESUMING" = false ]; then
  git checkout master 2>/dev/null
  git pull origin master 2>/dev/null

  # Block if there's an unmerged PR from a previous run.
  # We only work one issue at a time to avoid conflicts and missing context.
  OPEN_AUTO_PR=$(gh pr list --author "@me" --json number,title,headRefName --jq '[.[] | select(.headRefName | startswith("fix/issue-"))] | .[0] // empty' 2>/dev/null || true)
  if [ -n "$OPEN_AUTO_PR" ]; then
    OPEN_PR_NUM=$(echo "$OPEN_AUTO_PR" | jq -r '.number')
    OPEN_PR_TITLE=$(echo "$OPEN_AUTO_PR" | jq -r '.title')
    log "WAIT: PR #${OPEN_PR_NUM} (${OPEN_PR_TITLE}) is still open. Merge or close it before I start the next issue."
    exit 0
  fi

  log "Checking for open issues..."

  ISSUE=$(gh issue list --state open --json number,title,body --jq 'sort_by(.number) | .[0] // empty' 2>/dev/null)

  if [ -z "$ISSUE" ]; then
    log "No open issues found. Done."
    exit 0
  fi

  NUMBER=$(echo "$ISSUE" | jq -r '.number')
  TITLE=$(echo "$ISSUE" | jq -r '.title')
  BODY=$(echo "$ISSUE" | jq -r '.body')
  BRANCH="fix/issue-${NUMBER}"

  log "Working on issue #${NUMBER}: ${TITLE}"

  # Check if a PR already exists for this issue
  EXISTING_PR=$(gh pr list --search "issue-${NUMBER}" --json number --jq '.[0].number // empty' 2>/dev/null || true)
  if [ -n "$EXISTING_PR" ]; then
    log "SKIP: PR #${EXISTING_PR} already exists for issue #${NUMBER}"
    exit 0
  fi

  # Create or switch to the working branch
  if git rev-parse --verify "$BRANCH" >/dev/null 2>&1; then
    git checkout "$BRANCH"
  else
    git checkout -b "$BRANCH"
  fi

  # Save state so we can resume if interrupted
  jq -n \
    --arg number "$NUMBER" \
    --arg title "$TITLE" \
    --arg body "$BODY" \
    --arg branch "$BRANCH" \
    --arg status "in_progress" \
    '{number: $number, title: $title, body: $body, branch: $branch, status: $status}' \
    > "$STATE_FILE"
fi

log "Running Claude Code on issue #${NUMBER}..."

# Build the prompt — if resuming, tell Claude to continue where it left off
if [ "$RESUMING" = true ]; then
  CHANGES=$(git diff --stat HEAD 2>/dev/null || true)
  COMMITTED=$(git log master..HEAD --oneline 2>/dev/null || true)
  RESUME_CONTEXT="
IMPORTANT: This is a RESUMED session. A previous run was interrupted (likely by rate limiting).

Progress so far on this branch:
Commits since master:
${COMMITTED:-None yet}

Uncommitted changes:
${CHANGES:-None}

Review what has already been done. DO NOT redo work that is already committed or staged.
Continue from where the previous session left off. If the implementation looks complete,
just verify it works and commit any remaining changes.
"
else
  RESUME_CONTEXT=""
fi

CLAUDE_OUTPUT=$(claude -p "
You are an autonomous coding agent working on the dcn-demo repo.

IMPORTANT: Read the CLAUDE.md file first for full project context and architecture.
${RESUME_CONTEXT}
Your task is to implement a solution for this GitHub issue:

---
Issue #${NUMBER}: ${TITLE}

${BODY}
---

Follow this process:

1. PLAN: Analyze the codebase thoroughly. Identify every file that needs to change.
   List your plan step by step before writing any code.

2. IMPLEMENT: Make all the code changes needed. Be thorough — handle edge cases,
   follow existing patterns in the codebase, and don't leave TODOs.

3. TEST: If there are existing tests, make sure they still pass. If you're adding
   new functionality, add appropriate tests.

4. COMMIT: Stage all changed files and commit with a message like:
   fix: <short description>

   Closes #${NUMBER}

   - bullet points explaining what changed

Rules:
- Follow the existing code style exactly
- Don't add unnecessary comments that just describe what code does
- Don't modify files unrelated to the issue
- If the issue is too large or ambiguous, implement the most critical parts and
  note what else is needed in the PR description
" --allowedTools Bash,Read,Write,Edit,MultiEdit 2>&1) || true

echo "$CLAUDE_OUTPUT" >> "$LOG_FILE"

# Detect rate limiting
if echo "$CLAUDE_OUTPUT" | grep -qi "rate.limit\|hit your limit\|resets.*am\|resets.*pm"; then
  log "RATE LIMITED on issue #${NUMBER}. Saving progress for next run."

  # Commit any partial work so nothing is lost
  if [ -n "$(git status --porcelain)" ]; then
    git add -A
    git commit -m "$(cat <<EOF
wip: partial progress on issue #${NUMBER} (rate limited)

Work in progress — will be continued on next auto-worker run.
EOF
)" 2>/dev/null || true
    log "Saved partial work in WIP commit on branch ${BRANCH}"
  fi

  # State file stays as in_progress so next run resumes
  exit 0
fi

# ── Claude finished — check results ────────────────────────────
HAS_CHANGES=false
if [ -n "$(git status --porcelain)" ]; then
  HAS_CHANGES=true
fi
if [ -n "$(git log master..HEAD --oneline 2>/dev/null)" ]; then
  HAS_CHANGES=true
fi

if [ "$HAS_CHANGES" = false ]; then
  log "ERROR: Claude made no changes. Cleaning up."
  git checkout master
  git branch -D "$BRANCH" 2>/dev/null || true
  rm -f "$STATE_FILE"
  exit 1
fi

# Stage and commit any uncommitted work
if [ -n "$(git status --porcelain)" ]; then
  git add -A
  git commit -m "$(cat <<EOF
fix: implement solution for issue #${NUMBER}

Closes #${NUMBER}

Automated implementation by Claude Code agent.
EOF
)" 2>/dev/null || true
fi

# Squash any WIP commits into a clean history
WIP_COUNT=$(git log master..HEAD --oneline --grep="wip:" 2>/dev/null | wc -l | tr -d ' ')
if [ "$WIP_COUNT" -gt 0 ]; then
  git reset --soft master
  git commit -m "$(cat <<EOF
fix: implement solution for issue #${NUMBER}

Closes #${NUMBER}

Automated implementation by Claude Code agent.
EOF
)"
  log "Squashed ${WIP_COUNT} WIP commits into final commit"
fi

git push -u origin "$BRANCH" 2>&1 | tee -a "$LOG_FILE"

# Create the PR
gh pr create \
  --title "fix: ${TITLE}" \
  --body "$(cat <<EOF
## Summary

Automated implementation for #${NUMBER}.

Claude Code agent analyzed the issue, planned a solution, and implemented the changes on this branch.

## Issue

Closes #${NUMBER}

## Review Checklist

- [ ] Code changes match the issue requirements
- [ ] No unrelated files were modified
- [ ] Tests pass
- [ ] Code follows existing project patterns

---
*This PR was generated automatically by the DCN auto-worker agent.*
EOF
)" 2>&1 | tee -a "$LOG_FILE"

# Clean up state and go back to master
rm -f "$STATE_FILE"
git checkout master

log "Done with issue #${NUMBER}. PR created."
