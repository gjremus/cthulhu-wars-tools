#!/bin/zsh
# Backup MASTER TASK ticker — smart failsafe.
#
# Fires every 15 minutes. DOES NOT launch a Claude session unless the primary
# master task ticker is provably broken (hasn't fired or has been timing out).
#
# Gate logic:
#   1. Check /tmp/cw-ticker-master.history for last DONE with rc=0
#   2. If last successful tick was >20 min ago, the primary is stuck/dead
#   3. Check if launchd agent is loaded; reload if not
#   4. If still broken, fire a full master-task tick ourselves
#
# This catches the pattern where the master ticker gets killed (rc=143) or
# unloaded from launchd and stops processing the task doc.

set -u

export HOME="/Users/gremus"
export NODE_EXTRA_CA_CERTS="/Users/gremus/.claude/certs/salesforce-ca-bundle.pem"
export PATH="/Users/gremus/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

CLAUDE="/Users/gremus/.local/bin/claude"
PROMPT_FILE="/Users/gremus/Claude-Projects/cthulhu-wars-tools/tickers/prompt-master.txt"
WORKDIR="/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars"
CW="$WORKDIR"
TOOLS="/Users/gremus/Claude-Projects/cthulhu-wars-tools"

HIST="/tmp/cw-ticker-backup-master.history"
LOG="/tmp/cw-ticker-backup-master.$(date '+%Y%m%d').log"
PRIMARY_HIST="/tmp/cw-ticker-master.history"
PRIMARY_PLIST="$HOME/Library/LaunchAgents/com.gremus.cw-ticker-master.plist"
PRIMARY_LABEL="com.gremus.cw-ticker-master"

NOW=$(date +%s)

# ---- Step 1: Check when the primary master ticker last succeeded ----
LAST_OK_LINE=$(grep "DONE.*rc=0" "$PRIMARY_HIST" 2>/dev/null | tail -1)

if [[ -z "$LAST_OK_LINE" ]]; then
  # No successful tick ever recorded
  LAST_OK_AGE=99999
  echo "[$(date '+%F %T')] CHECK  no successful master tick found in history" >> "$HIST"
else
  # Extract timestamp from "[2026-07-08 22:31:49] DONE ..."
  LAST_OK_TS=$(echo "$LAST_OK_LINE" | grep -oE '\[([0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2})\]' | tr -d '[]')
  if [[ -n "$LAST_OK_TS" ]]; then
    LAST_OK_EPOCH=$(date -j -f "%Y-%m-%d %H:%M:%S" "$LAST_OK_TS" +%s 2>/dev/null)
    LAST_OK_AGE=$(( NOW - LAST_OK_EPOCH ))
  else
    LAST_OK_AGE=99999
  fi
fi

# ---- Step 2: If last success was < 20 min ago, primary is healthy ----
if [[ "$LAST_OK_AGE" -lt 1200 ]]; then
  echo "[$(date '+%F %T')] idle   master ticker healthy (last ok ${LAST_OK_AGE}s ago) — standing down" >> "$HIST"
  exit 0
fi

# ---- Step 3: Primary is behind. Check if it's running or stuck ----
echo "[$(date '+%F %T')] ALERT  master ticker behind (last ok ${LAST_OK_AGE}s ago) — diagnosing" >> "$HIST"

# Check if a tick is currently running (FIRED but no DONE after it)
LAST_FIRED=$(grep "FIRED" "$PRIMARY_HIST" 2>/dev/null | tail -1)
LAST_DONE=$(grep "DONE" "$PRIMARY_HIST" 2>/dev/null | tail -1)

# Extract timestamps for comparison
FIRED_TS=$(echo "$LAST_FIRED" | grep -oE '\[([0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2})\]' | tr -d '[]')
DONE_TS=$(echo "$LAST_DONE" | grep -oE '\[([0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2})\]' | tr -d '[]')

TICK_IN_PROGRESS=false
if [[ -n "$FIRED_TS" && -n "$DONE_TS" ]]; then
  FIRED_EPOCH=$(date -j -f "%Y-%m-%d %H:%M:%S" "$FIRED_TS" +%s 2>/dev/null)
  DONE_EPOCH=$(date -j -f "%Y-%m-%d %H:%M:%S" "$DONE_TS" +%s 2>/dev/null)
  if [[ "$FIRED_EPOCH" -gt "$DONE_EPOCH" ]]; then
    TICK_IN_PROGRESS=true
    TICK_RUNNING_FOR=$(( NOW - FIRED_EPOCH ))
  fi
elif [[ -n "$FIRED_TS" && -z "$DONE_TS" ]]; then
  TICK_IN_PROGRESS=true
  FIRED_EPOCH=$(date -j -f "%Y-%m-%d %H:%M:%S" "$FIRED_TS" +%s 2>/dev/null)
  TICK_RUNNING_FOR=$(( NOW - FIRED_EPOCH ))
fi

# If a tick has been running for < 25 min (the timeout), let it finish
if [[ "$TICK_IN_PROGRESS" == true && "$TICK_RUNNING_FOR" -lt 1500 ]]; then
  echo "[$(date '+%F %T')] wait   tick in progress for ${TICK_RUNNING_FOR}s (< timeout) — standing down" >> "$HIST"
  exit 0
fi

# ---- Step 4: Primary is stuck or dead. Try to reload launchd agent. ----
LOADED=$(launchctl print "gui/$(id -u)/$PRIMARY_LABEL" 2>&1)
if echo "$LOADED" | grep -q "Could not find service"; then
  echo "[$(date '+%F %T')] FIX    master ticker unloaded — reloading" >> "$HIST"
  launchctl bootstrap "gui/$(id -u)" "$PRIMARY_PLIST" 2>/dev/null
fi

# Kill any stuck master ticker processes
STUCK_PIDS=$(pgrep -f "run-ticker.sh.*master" 2>/dev/null)
if [[ -n "$STUCK_PIDS" ]]; then
  echo "[$(date '+%F %T')] FIX    killing stuck master ticker pids: $STUCK_PIDS" >> "$HIST"
  echo "$STUCK_PIDS" | xargs kill -TERM 2>/dev/null
  sleep 5
  echo "$STUCK_PIDS" | xargs kill -KILL 2>/dev/null
fi

# ---- Step 5: Fire the backup tick ourselves ----
echo "[$(date '+%F %T')] FIRING backup master tick (primary was behind ${LAST_OK_AGE}s)" >> "$HIST"
cd "$WORKDIR" || { echo "[$(date '+%F %T')] ABORT cd failed" >> "$HIST"; exit 1; }

TICK_TIMEOUT="${TICK_TIMEOUT:-1500}"

echo "===== [$(date '+%F %T')] backup master tick start (timeout ${TICK_TIMEOUT}s) =====" >> "$LOG"

"$CLAUDE" -p "$(cat "$PROMPT_FILE")" \
  --permission-mode bypassPermissions \
  --add-dir "$CW" \
  --add-dir "$TOOLS" \
  >> "$LOG" 2>&1 &
CLAUDE_PID=$!

(
  sleep "$TICK_TIMEOUT"
  if kill -0 "$CLAUDE_PID" 2>/dev/null; then
    echo "[$(date '+%F %T')] TIMEOUT  backup master tick pid=${CLAUDE_PID} exceeded ${TICK_TIMEOUT}s; killing" >> "$HIST"
    pkill -TERM -P "$CLAUDE_PID" 2>/dev/null
    kill -TERM "$CLAUDE_PID" 2>/dev/null
    sleep 10
    pkill -KILL -P "$CLAUDE_PID" 2>/dev/null
    kill -KILL "$CLAUDE_PID" 2>/dev/null
  fi
) &
WATCHDOG_PID=$!

wait "$CLAUDE_PID"
RC=$?

kill "$WATCHDOG_PID" 2>/dev/null
wait "$WATCHDOG_PID" 2>/dev/null

echo "===== [$(date '+%F %T')] backup master tick done rc=${RC} =====" >> "$LOG"
echo "[$(date '+%F %T')] DONE   backup master tick rc=${RC}" >> "$HIST"
exit "$RC"
