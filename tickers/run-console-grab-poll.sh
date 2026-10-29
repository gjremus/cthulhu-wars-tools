#!/bin/zsh
# Console-grab POLL ticker.
#
# Fires frequently (every ~2 min via its plist). Reads the shared admin queue
# (claude-prompts-log), finds NEW lines tagged:
#     CONSOLE-CHECK game=<id> build=<build>
# and runs tools/console-grab.py for each. The runner loads the game in headless
# Chromium LOCALLY (the VM is too small for Chromium) and writes the captured
# console errors into the game's annotation Notes.
#
# This ticker does NOT spend an AI session — it's a plain shell + python loop, so
# it's cheap to run often.
#
# "New" is tracked by a high-water-mark timestamp file (/tmp/cw-console-grab.seen):
# we only act on queue lines whose "[YYYY-MM-DD HH:MM:SS]" stamp is strictly
# greater than the last one we processed. This is independent of the server-side
# ack used by the AI admin ticker, so the two don't interfere.
#
# Why the explicit env: launchd does NOT source the shell profile, so the
# Salesforce CA bundle (TLS through the corporate proxy) and PATH must be set
# here or curl/python fail.

set -u

export HOME="/Users/gremus"
export NODE_EXTRA_CA_CERTS="/Users/gremus/.claude/certs/salesforce-ca-bundle.pem"
export PATH="/Users/gremus/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

TOOLS="/Users/gremus/Claude-Projects/cthulhu-wars-tools"
RUNNER="${TOOLS}/tools/console-grab.py"
TOKEN_FILE="/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars/Library at Celaeno/Server Deployment/owner-admin-token.txt"

HIST="/tmp/cw-console-grab-poll.history"
LOG="/tmp/cw-console-grab-poll.$(date '+%Y%m%d').log"
SEEN="/tmp/cw-console-grab.seen"   # high-water timestamp "YYYY-MM-DD HH:MM:SS"

# Token read with off-Drive cache fallback (Drive intermittently dehydrates it).
TOK_CACHE="/Users/gremus/.cw-admin-token"
TOK=$(tr -d '[:space:]' < "$TOKEN_FILE" 2>/dev/null)
if [[ -n "$TOK" ]]; then
  print -r -- "$TOK" > "$TOK_CACHE" 2>/dev/null
else
  TOK=$(tr -d '[:space:]' < "$TOK_CACHE" 2>/dev/null)
fi
if [[ -z "$TOK" ]]; then
  echo "[$(date '+%F %T')] ABORT  no admin token (Drive dehydrated AND no cache)" >> "$HIST"; exit 1
fi

# Pull the queue with ?all=true so server-side acks (used by the AI ticker)
# don't hide CONSOLE-CHECK lines from us before we've run them.
URL="https://cwo.freeddns.org/admin/${TOK}/claude-prompts-log?lines=400&all=true"
RAW=$(curl -s --max-time 30 "$URL")
if [[ -z "$RAW" ]]; then
  echo "[$(date '+%F %T')] idle   queue empty/unreachable" >> "$HIST"
  exit 0
fi

LAST_SEEN=$(cat "$SEEN" 2>/dev/null)

# Extract CONSOLE-CHECK lines newer than LAST_SEEN. Each queue line looks like:
#   [2026-06-14 19:13:00] CONSOLE-CHECK game=454 build=mnu
# We emit "<ts>\t<id>\t<build>" for the matching, newer lines. Parsing is done
# in python3 (already required by the runner) because macOS's BSD awk lacks the
# 3-arg match()/capture-array gawk extension.
NEW=$(LAST_SEEN="$LAST_SEEN" python3 - "$RAW" <<'PYEOF'
import os, re, sys
raw = sys.argv[1] if len(sys.argv) > 1 else ""
last = os.environ.get("LAST_SEEN", "")
pat = re.compile(
    r'^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]\s+'
    r'CONSOLE-CHECK\s+game=(\d+)\s+build=(\w+)')
for line in raw.splitlines():
    m = pat.match(line.strip())
    if m:
        ts, gid, build = m.group(1), m.group(2), m.group(3)
        if ts > last:
            print(f"{ts}\t{gid}\t{build}")
PYEOF
)

if [[ -z "$NEW" ]]; then
  echo "[$(date '+%F %T')] idle   no new CONSOLE-CHECK lines" >> "$HIST"
  exit 0
fi

echo "===== [$(date '+%F %T')] console-grab poll start =====" >> "$LOG"
MAXTS="$LAST_SEEN"
COUNT=0
# Use process substitution (not a pipe) so MAXTS/COUNT updates land in THIS
# shell — a piped `while` runs in a subshell and would lose them.
while IFS=$'\t' read -r TS ID BUILD; do
  [[ -z "$ID" ]] && continue
  COUNT=$((COUNT+1))
  echo "[$(date '+%F %T')] RUN    game=$ID build=$BUILD (queued $TS)" >> "$LOG"
  python3 "$RUNNER" --game "$ID" --build "$BUILD" >> "$LOG" 2>&1
  RC=$?
  echo "[$(date '+%F %T')] DONE   game=$ID rc=$RC" >> "$LOG"
  # Advance the high-water mark even on a single-game failure: console-grab.py is
  # idempotent and a failing game shouldn't wedge the queue. The hourly sweep
  # will re-cover active games anyway.
  if [[ "$TS" > "$MAXTS" ]]; then MAXTS="$TS"; fi
done < <(print -r -- "$NEW")

# Persist the new high-water mark so we don't re-run these lines next tick.
if [[ -n "$MAXTS" ]]; then print -r -- "$MAXTS" > "$SEEN"; fi
echo "===== [$(date '+%F %T')] console-grab poll done (new mark: $MAXTS) =====" >> "$LOG"
echo "[$(date '+%F %T')] DONE   processed $COUNT new CONSOLE-CHECK line(s)" >> "$HIST"
exit 0
