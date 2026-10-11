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

# run_claude <model> <haiku|sonnet> <max seconds> <ids_array_var>
# Relaunches if nothing is printed within 90 s (the launchd startup deadlock seen by the
# unified ticker), then waits up to <max seconds> before killing. Posts cost split evenly
# over the request ids in the array variable named in $4.
run_claude() {
    local model="$1" mode="$2" max="$3" ids_var="$4" out="/tmp/cw-designer-extract.$2.jsonl" try pid waited
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
        # Post cost split evenly over the request ids
        python3 - "$out" "$mode" "$ids_var" "$TICKERS" >> "$LOG" <<'PY'
import json, os, subprocess, sys, time
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
    cost = res.get('total_cost_usd', 0) or 0
    print(f"[{stamp}] {sys.argv[2]} ${cost:.4f} {text[:400]}")
    # Split cost evenly over request ids
    ids_var = sys.argv[3]
    ids = os.environ.get(ids_var, '').strip().split()
    if ids and cost > 0:
        per_id = cost / len(ids)
        tickers = sys.argv[4]
        for rid in ids:
            try:
                subprocess.run([
                    'python3', f'{tickers}/designer-admin.py',
                    'tlog-cost', rid, str(per_id), '--add'
                ], check=True, capture_output=True, timeout=10)
                print(f"[{stamp}] posted ${per_id:.4f} to {rid}")
            except Exception as e:
                print(f"[{stamp}] failed to post cost to {rid}: {e}")
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

# Record pending request ids (terminal log row ids) before the Haiku run
haiku_ids=$(print -r -- "$pending" | python3 -c 'import json, sys; reqs = json.load(sys.stdin); print(" ".join(r["id"] for r in reqs))')
export HAIKU_IDS="$haiku_ids"
run_claude "$HAIKU" haiku 600 HAIKU_IDS

if [[ -s "$HANDOFF" ]]; then
    # Record handed-off request ids before the Sonnet run
    sonnet_ids=$(python3 -c 'import json; handed = json.load(open("'"$HANDOFF"'")); print(" ".join(h["id"] for h in handed))')
    export SONNET_IDS="$sonnet_ids"
    run_claude "$SONNET" sonnet 2700 SONNET_IDS
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
