#!/bin/zsh
# Telegram ticker runner (primary).
#
# Token-efficient by design: SSHes to the server to SHA the raw prompts log,
# and only launches a full `claude -p` session when the queue has CHANGED since
# the last run. An unchanged queue costs one cheap SSH call, not an AI session.
#
# launchd serializes per-label, so overlapping runs can't stack.

set -u

export HOME="/Users/gremus"
export NODE_EXTRA_CA_CERTS="/Users/gremus/.claude/certs/salesforce-ca-bundle.pem"
export PATH="/Users/gremus/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

CLAUDE="/Users/gremus/.local/bin/claude"
PROMPT_FILE="/Users/gremus/Claude-Projects/cthulhu-wars-tools/tickers/prompt-admin.txt"
WORKDIR="/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars"
CW="$WORKDIR"
TOOLS="/Users/gremus/Claude-Projects/cthulhu-wars-tools"
PROJECTS="/Users/gremus/claude-projects"

SSH_KEY="/Users/gremus/.ssh/oracle_cw_ed25519"
SSH_HOST="oracle-cw-server@35.255.125.91"
SSH_OPTS=(-i "$SSH_KEY" -o ConnectTimeout=10 -o StrictHostKeyChecking=no)

HIST="/tmp/cw-ticker-telegram.history"
LOG="/tmp/cw-ticker-telegram.$(date '+%Y%m%d').log"
SEEN="/tmp/cw-telegram-lastseen.sha"

# ---- cheap gate: has the prompts log changed? (SSH to read raw file) ----
CUR=$(ssh "${SSH_OPTS[@]}" "$SSH_HOST" "sha1sum /tmp/claude-prompts.log 2>/dev/null" | cut -d' ' -f1)
if [[ -z "$CUR" ]]; then
  echo "[$(date '+%F %T')] SKIP   server unreachable or prompts log missing" >> "$HIST"
  exit 0
fi
PREV=$(cat "$SEEN" 2>/dev/null)
if [[ "$CUR" == "$PREV" ]]; then
  echo "[$(date '+%F %T')] idle   prompts log unchanged — no AI session spent" >> "$HIST"
  exit 0
fi

# ---- new activity: spend a full tick ----
TICK_TIMEOUT="${TICK_TIMEOUT:-1500}"  # 25 min hard kill (matches master ticker)

echo "[$(date '+%F %T')] NEW    prompts log changed -> running tick" >> "$HIST"
cd "$WORKDIR" || { echo "[$(date '+%F %T')] ABORT cd failed" >> "$HIST"; exit 1; }

echo "===== [$(date '+%F %T')] telegram tick start (timeout ${TICK_TIMEOUT}s) =====" >> "$LOG"
"$CLAUDE" -p "$(cat "$PROMPT_FILE")" \
  --permission-mode bypassPermissions \
  --add-dir "$CW" --add-dir "$TOOLS" --add-dir "$PROJECTS" \
  >> "$LOG" 2>&1 &
CLAUDE_PID=$!

(
  sleep "$TICK_TIMEOUT"
  if kill -0 "$CLAUDE_PID" 2>/dev/null; then
    echo "[$(date '+%F %T')] TIMEOUT  telegram tick pid=${CLAUDE_PID} exceeded ${TICK_TIMEOUT}s; killing" >> "$HIST"
    echo "===== [$(date '+%F %T')] telegram TIMEOUT after ${TICK_TIMEOUT}s — killing =====" >> "$LOG"
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

echo "===== [$(date '+%F %T')] telegram tick done rc=${RC} =====" >> "$LOG"

# Re-read the SHA AFTER the tick so we only re-fire on genuinely new submissions.
# Only save on a clean tick — a failed tick re-tries next cycle.
if [[ "$RC" -eq 0 ]]; then
  NEW=$(ssh "${SSH_OPTS[@]}" "$SSH_HOST" "sha1sum /tmp/claude-prompts.log 2>/dev/null" | cut -d' ' -f1)
  [[ -n "$NEW" ]] && echo "$NEW" > "$SEEN"
fi
echo "[$(date '+%F %T')] DONE   telegram tick rc=${RC}" >> "$HIST"

# Escalate if failing too long
"$(dirname "$0")/escalate-on-failure.sh" "telegram" "$RC"

exit "$RC"
