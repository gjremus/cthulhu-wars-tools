#!/bin/zsh
# Live-game health ticker.
#
# Fires every 15 min (via its plist). Fetches the list of live-flagged games
# from the server, then runs console-grab.py on each one. If a game has
# console errors, auto-submits to the Claude prompts queue for triage.
#
# Plain shell + python — spends no AI session.

set -u

export HOME="/Users/gremus"
export NODE_EXTRA_CA_CERTS="/Users/gremus/.claude/certs/salesforce-ca-bundle.pem"
export PATH="/Users/gremus/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

TOOLS="/Users/gremus/Claude-Projects/cthulhu-wars-tools"
RUNNER="${TOOLS}/tools/console-grab.py"

LOG="/tmp/cw-live-game-check.$(date '+%Y%m%d').log"
HIST="/tmp/cw-live-game-check.history"

echo "===== [$(date '+%F %T')] live-game check start =====" >> "$LOG"
echo "[$(date '+%F %T')] FIRED  live-game check" >> "$HIST"

# Read token (try cache first since Drive can deadlock)
TOKEN_CACHE="/Users/gremus/.cw-admin-token"
TOKEN_FILE="/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars/Maps/Library at Celaeno/Server Deployment/owner-admin-token.txt"

TOKEN=""
if [[ -f "$TOKEN_CACHE" && -s "$TOKEN_CACHE" ]]; then
    TOKEN="$(cat "$TOKEN_CACHE")"
fi
if [[ -z "$TOKEN" && -f "$TOKEN_FILE" ]]; then
    TOKEN="$(cat "$TOKEN_FILE" 2>/dev/null)" || true
fi
if [[ -z "$TOKEN" ]]; then
    echo "[$(date '+%F %T')] ERROR: cannot read admin token" >> "$LOG"
    exit 1
fi

# Fetch live-flagged game IDs
LIVE_IDS=$(curl -s --max-time 15 "https://cwo.freeddns.org/admin/${TOKEN}/live-games" 2>/dev/null)
if [[ -z "$LIVE_IDS" ]]; then
    echo "[$(date '+%F %T')] No live-flagged games (or server unreachable)" >> "$LOG"
    echo "[$(date '+%F %T')] DONE   live-game check (0 games)" >> "$HIST"
    exit 0
fi

COUNT=0
ERRORED=0
while IFS= read -r GAME_ID; do
    [[ -z "$GAME_ID" ]] && continue
    COUNT=$((COUNT + 1))
    echo "[$(date '+%F %T')] Checking game $GAME_ID ..." >> "$LOG"

    # Run console-grab for this game (auto-detects build from server data)
    OUTPUT=$(python3 "$RUNNER" --game "$GAME_ID" 2>&1)
    RC=$?
    echo "$OUTPUT" >> "$LOG"

    # If console-grab flagged it broken (rc=2 means errors found and annotation written),
    # auto-submit to the Claude prompts queue for triage
    if [[ $RC -eq 2 ]]; then
        ERRORED=$((ERRORED + 1))
        PROMPT="CONSOLE-CHECK game=${GAME_ID} build=auto — LIVE-GAME AUTO-CHECK found console errors. Game was auto-flagged broken by the live-game health ticker. Please investigate and fix."
        curl -s --max-time 10 -X POST \
            "https://cwo.freeddns.org/admin/${TOKEN}/claude-prompt" \
            -d "$PROMPT" >> "$LOG" 2>&1
        echo "[$(date '+%F %T')] Auto-submitted error report for game $GAME_ID" >> "$LOG"
    fi
done <<< "$LIVE_IDS"

echo "===== [$(date '+%F %T')] live-game check done: $COUNT games, $ERRORED errored =====" >> "$LOG"
echo "[$(date '+%F %T')] DONE   live-game check ($COUNT games, $ERRORED errored)" >> "$HIST"
exit 0
