#!/bin/zsh
# Daily audit ticker — lightweight (NO Claude session spawned).
# Pauses other tickers, writes an admin prompt so the master ticker runs
# a full daily audit (documentation check + stale-build check), then the
# master resumes tickers when done.
#
# Fires once daily at 03:00 CDT via launchd.
# Install:
#   launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.gremus.cw-daily-audit.plist
# Uninstall:
#   launchctl bootout   gui/$(id -u) ~/Library/LaunchAgents/com.gremus.cw-daily-audit.plist

set -u

export HOME="/Users/gremus"
export PATH="/Users/gremus/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

SSH_KEY="$HOME/.ssh/oracle_cw_ed25519"
SSH_HOST="oracle-cw-server@35.255.125.91"
SSH_OPTS=(-i "$SSH_KEY" -o ConnectTimeout=10 -o StrictHostKeyChecking=no)

HIST="/tmp/cw-daily-audit.history"
UID_NUM=$(id -u)

echo "[$(date '+%F %T')] FIRED daily audit" >> "$HIST"

# Step 1: Pause non-master tickers so they don't interfere with the audit
TICKERS_TO_PAUSE=(
  com.gremus.cw-ticker-backup
  com.gremus.cw-ticker-homebrews
  com.gremus.cw-ticker-fbe-tasks
  com.gremus.cw-ticker-library
  com.gremus.cw-ticker-admin
  com.gremus.claude-ticker-bb
  com.gremus.claude-ticker-tt
)

for t in "${TICKERS_TO_PAUSE[@]}"; do
  if launchctl list "$t" &>/dev/null; then
    launchctl bootout "gui/$UID_NUM/$t" 2>/dev/null
    echo "[$(date '+%F %T')] PAUSED $t" >> "$HIST"
  fi
done

# Step 2: Write daily-audit prompt to admin queue on server
PROMPT="DAILY-AUDIT $(date '+%F'): Pause confirmed. Run the daily end-of-day audit: (1) check that ALL fixes deployed today have proper rollback guide entries, (2) audit all builds (Library, MNU, TT, BB, HB) for stale deploys — compare the deployed cache tag to the most recent compiled source, (3) when done, resume paused tickers by running: for t in com.gremus.cw-ticker-backup com.gremus.cw-ticker-homebrews com.gremus.cw-ticker-fbe-tasks com.gremus.cw-ticker-library com.gremus.cw-ticker-admin com.gremus.claude-ticker-bb com.gremus.claude-ticker-tt; do launchctl bootstrap gui/\$(id -u) ~/Library/LaunchAgents/\$t.plist 2>/dev/null; done"

ssh "${SSH_OPTS[@]}" "$SSH_HOST" "echo '${PROMPT}' >> /tmp/claude-admin-prompts.log" 2>/dev/null
RC=$?

if [[ $RC -eq 0 ]]; then
  echo "[$(date '+%F %T')] DONE   prompt written to server queue" >> "$HIST"
else
  echo "[$(date '+%F %T')] ERROR  ssh failed rc=$RC — resuming tickers immediately" >> "$HIST"
  # If SSH failed, resume tickers so they don't stay paused
  for t in "${TICKERS_TO_PAUSE[@]}"; do
    plist="$HOME/Library/LaunchAgents/${t}.plist"
    if [[ -f "$plist" ]]; then
      launchctl bootstrap "gui/$UID_NUM" "$plist" 2>/dev/null
    fi
  done
fi

exit $RC
