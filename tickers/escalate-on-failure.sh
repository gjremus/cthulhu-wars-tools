#!/bin/zsh
# Escalation check: if a ticker has failed (TIMEOUT/non-zero rc) for 30+ min
# straight, write to the escalation file so the next Claude Code session picks
# up the work directly.
#
# Called at the end of run-ticker.sh and run-admin-ticker.sh on failure.
# Usage: escalate-on-failure.sh <ticker-name> <rc>

set -u

TICKER="${1:?ticker name required}"
RC="${2:?rc required}"
ESCALATION_DIR="/tmp/cwo-ticker-escalations"
ESCALATION_FILE="$ESCALATION_DIR/${TICKER}.escalation"
HISTORY_FILE="/tmp/cw-ticker-${TICKER}.history"

mkdir -p "$ESCALATION_DIR"

# If tick succeeded, clear any existing escalation
if [[ "$RC" -eq 0 ]]; then
    rm -f "$ESCALATION_FILE"
    exit 0
fi

# Tick failed — check how long we've been failing
# Look at the history for the last successful tick
LAST_SUCCESS=$(grep "DONE.*rc=0" "$HISTORY_FILE" 2>/dev/null | tail -1 | grep -o '\[[0-9-]* [0-9:]*\]' | tr -d '[]')
if [[ -z "$LAST_SUCCESS" ]]; then
    LAST_SUCCESS="never"
    FAIL_DURATION=9999
else
    LAST_SUCCESS_EPOCH=$(date -j -f "%Y-%m-%d %H:%M:%S" "$LAST_SUCCESS" "+%s" 2>/dev/null || echo 0)
    NOW_EPOCH=$(date "+%s")
    FAIL_DURATION=$(( (NOW_EPOCH - LAST_SUCCESS_EPOCH) / 60 ))
fi

# If failing for 30+ min, escalate
if [[ "$FAIL_DURATION" -ge 30 ]]; then
    cat > "$ESCALATION_FILE" <<EOF
ticker=$TICKER
failing_since=$LAST_SUCCESS
fail_duration_min=$FAIL_DURATION
last_rc=$RC
timestamp=$(date '+%F %T')
reason=Ticker has been failing for ${FAIL_DURATION} minutes. Likely cause: corporate proxy (sfproxy) choking on concurrent Claude sessions, or API hang. Action needed: reduce concurrent tickers, retry the work directly, or investigate proxy.
EOF
    echo "[$(date '+%F %T')] ESCALATED  ticker=${TICKER} failing for ${FAIL_DURATION}m" >> "$HISTORY_FILE"
fi
