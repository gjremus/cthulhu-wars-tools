#!/bin/zsh
# Generic launchd-driven Cthulhu Wars ticker runner.
# Invoked by the per-ticker .plist files in ~/Library/LaunchAgents/.
#
# Usage: run-ticker.sh <ticker-name> <prompt-file> <workdir>
#
# launchd serializes per-label: it will NOT start a second copy of the same
# job while the previous one is still running, so overlapping long ticks are
# already prevented without flock (macOS has no flock anyway).
#
# CAVEAT (the reason for the watchdog below): that same serialization means a
# single tick that hangs or runs for hours wedges the entire schedule -- no new
# tick fires until the stuck one dies, and the task docs go stale. So every tick
# is now run under a hard TICK_TIMEOUT and killed if it overruns.
#
# Why the explicit env: launchd does NOT source your shell profile, so the
# Salesforce CA bundle (needed for TLS through the corporate proxy) and the
# PATH to the claude binary must be set here or the tick fails with cert/
# command-not-found errors.

set -u

TICKER="${1:?ticker name required}"
PROMPT_FILE="${2:?prompt file required}"
WORKDIR="${3:?workdir required}"

export HOME="/Users/gremus"
export NODE_EXTRA_CA_CERTS="/Users/gremus/.claude/certs/salesforce-ca-bundle.pem"
export PATH="/Users/gremus/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0

HIST="/tmp/cw-ticker-${TICKER}.history"
LOG="/tmp/cw-ticker-${TICKER}.$(date '+%Y%m%d').log"
CLAUDE="/Users/gremus/.local/bin/claude"

CW="/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars"
TOOLS="/Users/gremus/Claude-Projects/cthulhu-wars-tools"

echo "[$(date '+%F %T')] FIRED  ticker=${TICKER}" >> "$HIST"

if [[ ! -f "$PROMPT_FILE" ]]; then
  echo "[$(date '+%F %T')] ABORT  prompt file missing: $PROMPT_FILE" >> "$HIST"
  exit 1
fi

cd "$WORKDIR" || { echo "[$(date '+%F %T')] ABORT  cd failed: $WORKDIR" >> "$HIST"; exit 1; }

# Hard per-tick timeout. macOS ships no `timeout` binary, so we run the tick
# in the background and use a watchdog subshell to kill it if it overruns.
# Override per-ticker from the plist with the TICK_TIMEOUT env var (seconds).
TICK_TIMEOUT="${TICK_TIMEOUT:-1500}"   # default 25 min

echo "===== [$(date '+%F %T')] ${TICKER} tick start (timeout ${TICK_TIMEOUT}s) =====" >> "$LOG"

"$CLAUDE" -p "$(cat "$PROMPT_FILE")" \
  --permission-mode bypassPermissions \
  --add-dir "$CW" \
  --add-dir "$TOOLS" \
  >> "$LOG" 2>&1 &
CLAUDE_PID=$!

(
  sleep "$TICK_TIMEOUT"
  if kill -0 "$CLAUDE_PID" 2>/dev/null; then
    echo "[$(date '+%F %T')] TIMEOUT  ticker=${TICKER} pid=${CLAUDE_PID} exceeded ${TICK_TIMEOUT}s; killing" >> "$HIST"
    echo "===== [$(date '+%F %T')] ${TICKER} TIMEOUT after ${TICK_TIMEOUT}s -- killing tick =====" >> "$LOG"
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

# Tick finished on its own; cancel the watchdog so it doesn't linger.
kill "$WATCHDOG_PID" 2>/dev/null
wait "$WATCHDOG_PID" 2>/dev/null

echo "===== [$(date '+%F %T')] ${TICKER} tick done rc=${RC} =====" >> "$LOG"
echo "[$(date '+%F %T')] DONE   ticker=${TICKER} rc=${RC}" >> "$HIST"

# Escalate if failing too long
"$(dirname "$0")/escalate-on-failure.sh" "$TICKER" "$RC"

exit "$RC"
