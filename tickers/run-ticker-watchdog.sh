#!/bin/zsh
# Watchdog: monitors ticker health and sends a macOS notification + creates
# a "wake me up" prompt file when a ticker has been stuck for too long.
#
# This runs on a frequent schedule (every 5 min) and checks whether the
# master ticker has completed a successful tick within the last 30 min.
# If not, it:
#   1. Sends a macOS notification (osascript display notification)
#   2. Kills any stuck ticker processes
#   3. Writes a wake-up file that the next interactive Claude session can see
#
# Install:
#   launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.gremus.cw-ticker-watchdog.plist
#
# This does NOT run claude itself — it's a lightweight shell check.

set -u

export HOME="/Users/gremus"
export PATH="/Users/gremus/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

HISTORY="/tmp/cw-ticker-master.history"
WATCHDOG_LOG="/tmp/cw-ticker-watchdog.log"
ALERT_COOLDOWN_FILE="/tmp/cw-ticker-watchdog-last-alert"
WAKE_FILE="/tmp/cwo-ticker-wake-me-up"

# Cooldown: don't spam alerts more than once per 30 min
if [[ -f "$ALERT_COOLDOWN_FILE" ]]; then
    LAST_ALERT=$(stat -f %m "$ALERT_COOLDOWN_FILE")
    NOW=$(date +%s)
    ELAPSED=$(( NOW - LAST_ALERT ))
    if [[ $ELAPSED -lt 1800 ]]; then
        exit 0
    fi
fi

# Find last successful tick
LAST_SUCCESS_LINE=$(grep "DONE.*rc=0" "$HISTORY" 2>/dev/null | tail -1)
if [[ -z "$LAST_SUCCESS_LINE" ]]; then
    MINUTES_SINCE_SUCCESS=9999
else
    LAST_SUCCESS_TIME=$(echo "$LAST_SUCCESS_LINE" | grep -o '\[[0-9-]* [0-9:]*\]' | tr -d '[]')
    LAST_SUCCESS_EPOCH=$(date -j -f "%Y-%m-%d %H:%M:%S" "$LAST_SUCCESS_TIME" "+%s" 2>/dev/null || echo 0)
    NOW_EPOCH=$(date "+%s")
    MINUTES_SINCE_SUCCESS=$(( (NOW_EPOCH - LAST_SUCCESS_EPOCH) / 60 ))
fi

# If last success was within 30 min, all is well
if [[ $MINUTES_SINCE_SUCCESS -lt 30 ]]; then
    exit 0
fi

# ALERT: Master ticker has been failing for too long
echo "[$(date '+%F %T')] WATCHDOG ALERT: master ticker failing for ${MINUTES_SINCE_SUCCESS}m" >> "$WATCHDOG_LOG"

# 1. macOS notification
osascript -e "display notification \"Master ticker has been stuck for ${MINUTES_SINCE_SUCCESS} minutes. Last success: ${LAST_SUCCESS_TIME:-unknown}\" with title \"CWO Ticker STUCK\" sound name \"Sosumi\""

# 2. Kill any stuck master ticker claude processes (they'll be restarted by launchd)
STUCK_PIDS=$(pgrep -f "prompt-master" 2>/dev/null)
if [[ -n "$STUCK_PIDS" ]]; then
    echo "[$(date '+%F %T')] Killing stuck master ticker PIDs: $STUCK_PIDS" >> "$WATCHDOG_LOG"
    echo "$STUCK_PIDS" | xargs kill -TERM 2>/dev/null
    sleep 3
    echo "$STUCK_PIDS" | xargs kill -KILL 2>/dev/null
fi

# 3. Write wake-up file for next interactive Claude session
cat > "$WAKE_FILE" <<EOF
TICKER WATCHDOG ALERT
=====================
The master ticker has been stuck for ${MINUTES_SINCE_SUCCESS} minutes.
Last successful tick: ${LAST_SUCCESS_TIME:-never}
Time of alert: $(date '+%F %T')

The ticker keeps timing out (rc=143) with zero output — likely API rate limiting
from concurrent sessions. The watchdog killed the stuck processes; launchd will
restart at the next 15-min mark.

If this conversation is active: check if other Claude sessions are consuming API
quota. Kill competing processes with: pkill -f "prompt-fbe"; pkill -f "prompt-master"
Then wait for the next launchd fire and verify it produces output.
EOF

# Update cooldown
touch "$ALERT_COOLDOWN_FILE"

echo "[$(date '+%F %T')] Alert sent, cooldown set" >> "$WATCHDOG_LOG"
