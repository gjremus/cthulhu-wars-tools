#!/bin/zsh
# Dedicated admin-console ticker runner.
#
# Token-efficient by design: it CURLS the admin console prompt queue first and
# only launches a full `claude -p` session when the queue has CHANGED since the
# last run. An empty/unchanged queue costs one cheap HTTP call, not an AI session.
# This is what lets it run frequently (every 10 min) without burning the limit.
#
# launchd serializes per-label, so overlapping runs can't stack.

set -u

export HOME="/Users/gremus"
export NODE_EXTRA_CA_CERTS="/Users/gremus/.claude/certs/salesforce-ca-bundle.pem"
export PATH="/Users/gremus/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

CLAUDE="/Users/gremus/.local/bin/claude"
PROMPT_FILE="/Users/gremus/Claude-Projects/cthulhu-wars-tools/tickers/prompt-admin.txt"
WORKDIR="/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars"
TOKEN_FILE="/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars/Library at Celaeno/Server Deployment/owner-admin-token.txt"
CW="$WORKDIR"
TOOLS="/Users/gremus/Claude-Projects/cthulhu-wars-tools"
PROJECTS="/Users/gremus/claude-projects"

HIST="/tmp/cw-ticker-admin.history"
LOG="/tmp/cw-ticker-admin.$(date '+%Y%m%d').log"
SEEN="/tmp/cw-admin-lastseen.sha"

# Token read with off-Drive cache fallback. Google Drive intermittently dehydrates
# the token file (evicts its contents), which used to blank $TOK and abort every
# fire. Now: if the Drive copy reads non-empty, refresh the local cache; if it's
# dehydrated/empty, fall back to the cached copy so the ticker keeps working.
TOK_CACHE="/Users/gremus/.cw-admin-token"
TOK=$(tr -d '[:space:]' < "$TOKEN_FILE" 2>/dev/null)
if [[ -n "$TOK" ]]; then
  print -r -- "$TOK" > "$TOK_CACHE" 2>/dev/null
else
  TOK=$(tr -d '[:space:]' < "$TOK_CACHE" 2>/dev/null)
  [[ -n "$TOK" ]] && echo "[$(date '+%F %T')] NOTE   Drive token dehydrated — used off-Drive cache" >> "$HIST"
fi
if [[ -z "$TOK" ]]; then
  echo "[$(date '+%F %T')] ABORT  no admin token (Drive dehydrated AND no cache)" >> "$HIST"; exit 1
fi
URL="https://cwo.freeddns.org/admin/${TOK}/claude-prompts-log?lines=200"

# ---- cheap gate: has the admin queue changed? ----
CUR=$(curl -s --max-time 25 "$URL" | shasum | awk '{print $1}')
if [[ -z "$CUR" ]]; then
  echo "[$(date '+%F %T')] SKIP   admin log unreachable (server down/timeout)" >> "$HIST"
  exit 0
fi
PREV=$(cat "$SEEN" 2>/dev/null)
if [[ "$CUR" == "$PREV" ]]; then
  echo "[$(date '+%F %T')] idle   admin queue unchanged — no AI session spent" >> "$HIST"
  exit 0
fi

# ---- new activity: spend a full tick ----
echo "[$(date '+%F %T')] NEW    admin queue changed -> running tick" >> "$HIST"
cd "$WORKDIR" || { echo "[$(date '+%F %T')] ABORT cd failed" >> "$HIST"; exit 1; }

echo "===== [$(date '+%F %T')] admin tick start =====" >> "$LOG"
"$CLAUDE" -p "$(cat "$PROMPT_FILE")" \
  --permission-mode bypassPermissions \
  --add-dir "$CW" --add-dir "$TOOLS" --add-dir "$PROJECTS" \
  >> "$LOG" 2>&1
RC=$?
echo "===== [$(date '+%F %T')] admin tick done rc=${RC} =====" >> "$LOG"

# Re-read the queue AFTER the tick (absorbs any acks the tick itself appended)
# so we only re-fire on genuinely new submissions next time. Only save the
# marker on a clean tick — a failed tick re-tries next cycle.
if [[ "$RC" -eq 0 ]]; then
  NEW=$(curl -s --max-time 25 "$URL" | shasum | awk '{print $1}')
  [[ -n "$NEW" ]] && echo "$NEW" > "$SEEN"
fi
echo "[$(date '+%F %T')] DONE   admin tick rc=${RC}" >> "$HIST"
exit "$RC"
