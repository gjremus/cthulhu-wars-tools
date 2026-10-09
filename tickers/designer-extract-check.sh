#!/bin/zsh
# DESIGNER EXTRACT CHECKER (2026-10-09): launchd every 2 min (com.gremus.cw-designer-extract).
# Haiku checks the designer for open "extract" requests and does the extraction itself when it
# can; anything it can't do it hands off (designer-admin.py handoff), and this script then runs
# Sonnet on just those. Update/bug requests stay on the 15-min unified ticker.
# Same environment rules as run-all-tickers.sh: pinned claude (Full Disk Access), ticker python
# first on PATH, local workdir (Drive cwd → EINTR), explicit model ids (aliases may 401).

set -u
export HOME="/Users/gremus"
export NODE_EXTRA_CA_CERTS="/Users/gremus/.claude/certs/salesforce-ca-bundle.pem"
export PATH="/Users/gremus/.local/share/ticker-python/python/bin:/Users/gremus/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0

CLAUDE="/Users/gremus/.local/share/claude/ticker-claude-pinned"
TICKERS="/Users/gremus/Claude-Projects/cthulhu-wars-tools/tickers"
WORKDIR="/Users/gremus/.cw-ticker-workdir"
LOCK="/tmp/cw-designer-extract.lock"
HANDOFF="/tmp/cw-designer-extract-handoff.json"
ATTEMPTS="/tmp/cw-designer-extract-attempts.json"
LOG="/tmp/cw-designer-extract.$(date '+%Y%m%d').log"
HAIKU="claude-haiku-4-5-20251001"
SONNET="claude-sonnet-5"

# One run at a time: a Sonnet extraction can outlast the 2-min interval.
if ! mkdir "$LOCK" 2>/dev/null; then
    pid=$(cat "$LOCK/pid" 2>/dev/null)
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then exit 0; fi
    rm -rf "$LOCK"; mkdir "$LOCK" || exit 0
fi
echo $$ > "$LOCK/pid"
trap 'rm -rf "$LOCK"' EXIT

mkdir -p "$WORKDIR"; cd "$WORKDIR" || exit 1

prompt_for() {  # $1 = haiku|sonnet
    local base mode
    base=$(cat "$TICKERS/prompt-designer-extract.txt")
    mode=$(cat "$TICKERS/prompt-designer-extract-$1-mode.txt")
    print -r -- "${base//\{\{MODE\}\}/$mode}"
}

# run_claude <model> <haiku|sonnet> <max seconds>
# Relaunches if nothing is printed within 90 s (the launchd startup deadlock seen by the
# unified ticker), then waits up to <max seconds> before killing.
run_claude() {
    local model="$1" mode="$2" max="$3" out="/tmp/cw-designer-extract.$2.jsonl" try pid waited
    local prompt; prompt=$(prompt_for "$mode")
    for try in 1 2 3; do
        : > "$out"
        "$CLAUDE" -p "$prompt" --permission-mode bypassPermissions --model "$model" \
            --strict-mcp-config --output-format stream-json --verbose < /dev/null > "$out" 2>&1 &
        pid=$!
        waited=0
        while kill -0 $pid 2>/dev/null && [[ ! -s "$out" ]] && (( waited < 90 )); do sleep 2; (( waited += 2 )); done
        if kill -0 $pid 2>/dev/null && [[ ! -s "$out" ]]; then
            kill -9 $pid 2>/dev/null; echo "[$(date '+%F %T')] $mode startup hang, retry $try" >> "$LOG"; continue
        fi
        while kill -0 $pid 2>/dev/null && (( waited < max )); do sleep 2; (( waited += 2 )); done
        if kill -0 $pid 2>/dev/null; then
            kill -9 $pid 2>/dev/null; echo "[$(date '+%F %T')] $mode killed after ${max}s" >> "$LOG"
        fi
        wait $pid 2>/dev/null
        python3 - "$out" "$mode" >> "$LOG" <<'PY'
import json, sys, time
res = None
for line in open(sys.argv[1], errors='replace'):
    try:
        e = json.loads(line)
    except ValueError:
        continue
    if e.get('type') == 'result':
        res = e
stamp = time.strftime('%F %T')
if res is None:
    print(f"[{stamp}] {sys.argv[2]} no result line")
else:
    text = (res.get('result') or '').strip().replace('\n', ' | ')
    print(f"[{stamp}] {sys.argv[2]} ${res.get('total_cost_usd', 0):.4f} {text[:400]}")
PY
        return 0
    done
    return 1
}

# Free pre-check (owner chose this 2026-10-09): only start Haiku when something is waiting.
pending=$(python3 "$TICKERS/designer-admin.py" list-extract 2>>"$LOG")
if [[ $? -ne 0 ]]; then
    echo "[$(date '+%F %T')] pre-check failed (see error above); skipping" >> "$LOG"
    exit 0
fi
[[ "$(print -r -- "$pending" | tr -d ' \n')" == "[]" ]] && exit 0

run_claude "$HAIKU" haiku 600

if [[ -s "$HANDOFF" ]]; then
    run_claude "$SONNET" sonnet 2700
    # Count the try for every handed-off request; designer-admin.py stops listing one
    # (and alerts the owner) after 3 tries so a stuck request cannot loop forever.
    python3 - "$HANDOFF" "$ATTEMPTS" <<'PY'
import json, sys
try:
    handed = json.load(open(sys.argv[1]))
except (OSError, ValueError):
    handed = []
try:
    attempts = json.load(open(sys.argv[2]))
except (OSError, ValueError):
    attempts = {}
for h in handed:
    a = attempts.setdefault(h['id'], {})
    a['count'] = a.get('count', 0) + 1
json.dump(attempts, open(sys.argv[2], 'w'), indent=2)
PY
    rm -f "$HANDOFF"
fi
