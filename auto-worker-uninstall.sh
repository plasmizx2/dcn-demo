#!/bin/bash
# Removes the DCN auto-worker: cron job, state file, lock file, logs, and scripts.

echo "Removing DCN auto-worker..."

# Remove the cron job
crontab -l 2>/dev/null | grep -v "auto-worker.sh" | crontab - 2>/dev/null
echo "  ✓ Cron job removed"

# Remove the launchd agent (in case it was set up)
if [ -f ~/Library/LaunchAgents/com.dcn.autoworker.plist ]; then
  launchctl unload ~/Library/LaunchAgents/com.dcn.autoworker.plist 2>/dev/null
  rm -f ~/Library/LaunchAgents/com.dcn.autoworker.plist
  echo "  ✓ Launchd agent removed"
fi

# Remove lock file
rm -f /tmp/dcn-auto-worker.lock
echo "  ✓ Lock file removed"

# Remove state file, logs, and scripts
REPO_DIR="/Users/seandumont/Desktop/dcn-demo"
rm -f "$REPO_DIR/.auto-worker-state.json"
rm -f "$REPO_DIR/auto-worker.log"
rm -f "$REPO_DIR/auto-worker-stdout.log"
rm -f "$REPO_DIR/auto-worker-stderr.log"
rm -f "$REPO_DIR/auto-worker.sh"
echo "  ✓ State file, logs, and script removed"

# Clean up any leftover fix branches
cd "$REPO_DIR" 2>/dev/null
for branch in $(git branch --list 'fix/issue-*' 2>/dev/null); do
  git branch -D "$branch" 2>/dev/null
  echo "  ✓ Deleted branch $branch"
done

echo ""
echo "Done. Auto-worker fully removed."
echo "You can delete this script too: rm $REPO_DIR/auto-worker-uninstall.sh"
