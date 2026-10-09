#!/bin/zsh
# ADMIN CONSOLE WATCHER (2026-10-09): launchd every 2 min (com.gremus.cw-admin-queue).
# Watches the admin console's Claude Terminal queue (/tmp/claude-prompts.log on the VM) and hands
# each new submission to an Opus Claude Code agent run from $HOME, so it loads the same CLAUDE.md,
# memory and skills as the owner's own sessions.
#   tick (default): free check over SSH. New entries are moved off the VM into a local queue and
#                   shown in the console log as "queued". If no worker is running, one is started
#                   in the background, so ticks keep claiming new entries while the agent works.
#   worker:         runs the queue oldest-first, one agent at a time, posting each reply back to
#                   /tmp/claude-output.log (what the console's terminal log shows).
# Follow-ups resume the previous agent conversation if it ended less than RESUME_HOURS ago.
# Same environment rules as designer-extract-check.sh (pinned claude, explicit model id).

set -u
export HOME="/Users/gremus"
export NODE_EXTRA_CA_CERTS="/Users/gremus/.claude/certs/salesforce-ca-bundle.pem"
export PATH="/Users/gremus/.local/share/ticker-python/python/bin:/Users/gremus/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0

CLAUDE="/Users/gremus/.local/share/claude/ticker-claude-pinned"
TICKERS="/Users/gremus/Claude-Projects/cthulhu-wars-tools/tickers"
OPUS="claude-opus-5-5"
SSH=(ssh -i /Users/gremus/.ssh/oracle_cw_ed25519 -o ConnectTimeout=10 -o StrictHostKeyChecking=no oracle-cw-server@cwo.freeddns.org)
Q="/Users/gremus/.cw-admin-queue"          # pending/ running/ done/ + session state
CLAIM_LOCK="/tmp/cw-admin-queue.claim.lock"
WORKER_LOCK="/tmp/cw-admin-queue.worker.lock"
LOG="/tmp/cw-admin-queue.$(date '+%Y%m%d').log"
MAX_SECONDS=10800                          # 3 h per request
RESUME_HOURS=6

mkdir -p "$Q/pending" "$Q/running" "$Q/done"
note() { echo "[$(date '+%F %T')] $*" >> "$LOG"; }

# post_output <PROMPT|RESPONSE>  (body on stdin) -> console terminal log, stamped with VM time
post_output() {
    "${SSH[@]}" "f=/tmp/claude-output.log; printf '\n[$1 @%s] ' \"\$(date '+%F %T')\" >> \$f; cat >> \$f; echo >> \$f"
}

lock_alive() {  # $1 = lock dir
    local pid; pid=$(cat "$1/pid" 2>/dev/null)
    [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null
}

take_lock() {   # $1 = lock dir; fails if a live process holds it
    if ! mkdir "$1" 2>/dev/null; then
        lock_alive "$1" && return 1
        rm -rf "$1"; mkdir "$1" || return 1
    fi
    echo $$ > "$1/pid"
}

# ---------------------------------------------------------------- worker
if [[ "${1:-}" == "worker" ]]; then
    take_lock "$WORKER_LOCK" || exit 0
    trap 'rm -rf "$WORKER_LOCK"' EXIT
    cd "$HOME" || exit 1
    sysprompt=$(cat "$TICKERS/prompt-admin-queue-system.txt")
    # A request left in running/ means the last worker died mid-run: retry it first.
    for f in "$Q"/running/*(N); do [[ "${f:t}" == *.* ]] && rm -f "$f" || mv "$f" "$Q/pending/"; done
    while true; do
        item=( "$Q"/pending/*(N.on) ); (( ${#item} )) || break   # names start with epoch: oldest first
        job="$Q/running/${item[1]:t}"; mv "${item[1]}" "$job"
        text=$(cat "$job")
        out="$job.jsonl"
        resume=()
        if [[ -s "$Q/session" ]] && [[ -n "$(find "$Q/session" -mmin -$(( RESUME_HOURS * 60 )) 2>/dev/null)" ]]; then
            resume=(--resume "$(cat "$Q/session")")
        fi
        note "start ${job:t} ${resume:+(resume)} :: ${text[1,120]//$'\n'/ }"
        started=0
        for try in 1 2 3; do
            : > "$out"
            "$CLAUDE" -p "$text" "${resume[@]}" --append-system-prompt "$sysprompt" \
                --permission-mode bypassPermissions --model "$OPUS" --strict-mcp-config \
                --output-format stream-json --verbose < /dev/null > "$out" 2>&1 &
            pid=$!; waited=0
            # Relaunch if nothing is printed within 90 s (launchd startup deadlock seen before).
            while kill -0 $pid 2>/dev/null && [[ ! -s "$out" ]] && (( waited < 90 )); do sleep 2; (( waited += 2 )); done
            if kill -0 $pid 2>/dev/null && [[ ! -s "$out" ]]; then
                kill -9 $pid 2>/dev/null; note "startup hang, retry $try"; continue
            fi
            started=1
            while kill -0 $pid 2>/dev/null && (( waited < MAX_SECONDS )); do sleep 5; (( waited += 5 )); done
            if kill -0 $pid 2>/dev/null; then kill -9 $pid 2>/dev/null; note "killed after ${MAX_SECONDS}s"; fi
            wait $pid 2>/dev/null
            # An old conversation that will not resume: start a fresh one instead.
            if (( ${#resume} )) && ! grep -q '"type":"result"' "$out"; then
                note "resume failed, starting a fresh conversation"; resume=(); started=0; continue
            fi
            break
        done
        # Pull the reply, cost and session id out of the stream.
        python3 - "$out" "$Q/session" "$job.reply" "$started" >> "$LOG" <<'PY'
import json, sys, time
out, session_file, reply_file, started = sys.argv[1:5]
res, sid = None, None
for line in open(out, errors='replace'):
    try:
        e = json.loads(line)
    except ValueError:
        continue
    sid = e.get('session_id') or sid
    if e.get('type') == 'result':
        res = e
if sid:
    open(session_file, 'w').write(sid)
if res and (res.get('result') or '').strip():
    reply = res['result'].strip()
elif started == '1':
    reply = ("Terribly sorry - the agent stopped before it could write a reply (it may have run "
             "out of time). Whatever it finished is kept; please send the request again to carry on.")
else:
    reply = "Very sorry - the agent would not start (3 tries). Please send the request again in a few minutes."
open(reply_file, 'w').write(reply + '\n')
cost = (res or {}).get('total_cost_usd', 0) or 0
print(f"[{time.strftime('%F %T')}] done ${cost:.4f} {reply[:300].replace(chr(10), ' | ')}")
PY
        # Start the reply with the first words of the request, so replies that come back after
        # a queue are easy to match to what was asked.
        { print -r -- "(re: ${${text//$'\n'/ }[1,70]}...)"; cat "$job.reply"; } | post_output RESPONSE || note "could not post reply to the console"
        # Telegram-tagged entries also want a one-line answer in the responses file.
        tg=$(print -r -- "$text" | grep -oE '\[TGMSG_[A-Za-z0-9_-]+\]' | head -1 | tr -d '[]')
        if [[ -n "$tg" ]]; then
            { printf '%s|' "$tg"; tr '\n' ' ' < "$job.reply"; echo; } | "${SSH[@]}" "cat >> /tmp/claude-prompt-responses.log"
        fi
        mv "$job" "$job.jsonl" "$job.reply" "$Q/done/" 2>/dev/null
    done
    exit 0
fi

# ---------------------------------------------------------------- tick
take_lock "$CLAIM_LOCK" || exit 0
trap 'rm -rf "$CLAIM_LOCK"' EXIT

# Claim everything waiting on the VM. The file is moved aside first so new submissions start a
# fresh file; .claim is only deleted after the entries are safely queued here.
raw=$("${SSH[@]}" 'f=/tmp/claude-prompts.log; [ -s $f ] && mv $f $f.claim.$$ && sleep 1; cat $f.claim.* 2>/dev/null; true' 2>>"$LOG")
if [[ $? -ne 0 ]]; then note "server check failed"; exit 0; fi

if [[ -n "$raw" ]]; then
    # Entries look like "[YYYY-MM-DD HH:MM:SS] text" and the text may span several lines.
    new=$(print -r -- "$raw" | python3 -c '
import re, sys, time, os
q = sys.argv[1]
raw = sys.stdin.read()
parts = re.split(r"(?m)^\[(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)\] ", raw)
n = 0
for i in range(1, len(parts), 2):
    text = parts[i + 1].strip()
    if not text:
        continue
    n += 1
    name = "%d-%03d" % (time.time(), n)
    open(os.path.join(q, "pending", name), "w").write(text + "\n")
    print(name)
' "$Q") || { note "could not queue claimed entries; left on server"; exit 0; }
    "${SSH[@]}" 'rm -f /tmp/claude-prompts.log.claim.*'
    note "queued: ${new//$'\n'/ }"
    # Show each new entry in the console log right away, with its place in line.
    for name in ${(f)new}; do
        older=( "$Q"/running/<->-<->(N) )
        for a in "$Q"/pending/*(N); do [[ "${a:t}" < "$name" ]] && older+=( $a ); done
        msg="(queued for the Opus agent"; (( ${#older} )) && msg+=" - ${#older} ahead of it"; msg+=")"
        { cat "$Q/pending/$name"; echo "$msg"; } | post_output PROMPT || note "could not post queued notice"
    done
fi

# Something waiting and nobody working on it -> start a worker in the background.
waiting=( "$Q"/pending/*(N) "$Q"/running/*(N) )
if (( ${#waiting} )) && ! lock_alive "$WORKER_LOCK"; then
    nohup /bin/zsh "$0" worker >> "$LOG" 2>&1 &
    note "worker started"
fi
exit 0
