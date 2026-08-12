#!/bin/zsh
# UNIFIED TICKER RUNNER: runs ALL tickers sequentially in one launchd job.
# Fires every 15 minutes. Each tick gets the master, homebrews, and FBE prompts
# executed one at a time — no parallel claude sessions, no API throttling.
#
# THIS IS THE ONLY TICKER MECHANISM. All individual per-ticker launchd jobs
# have been unloaded. If you need to restart:
#   launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.gremus.cw-ticker-unified.plist
# To stop:
#   launchctl bootout gui/$(id -u)/com.gremus.cw-ticker-unified

set -u

export HOME="/Users/gremus"
export NODE_EXTRA_CA_CERTS="/Users/gremus/.claude/certs/salesforce-ca-bundle.pem"
export PATH="/Users/gremus/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0

CLAUDE="/Users/gremus/.local/bin/claude"
TOOLS="/Users/gremus/Claude-Projects/cthulhu-wars-tools"
CW="/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars"
LOCKFILE="/tmp/cw-ticker-unified.lock"

# Mutual exclusion: if another instance is already running, bail
if [[ -f "$LOCKFILE" ]]; then
    LOCK_PID=$(cat "$LOCKFILE" 2>/dev/null)
    if kill -0 "$LOCK_PID" 2>/dev/null; then
        echo "[$(date '+%F %T')] SKIP unified ticker — previous run (pid $LOCK_PID) still active" >> /tmp/cw-ticker-unified.history
        exit 0
    fi
    # Stale lock — previous run crashed
    rm -f "$LOCKFILE"
fi
echo $$ > "$LOCKFILE"
trap 'rm -f "$LOCKFILE"' EXIT

# ── Progress-based watchdog (replaces the old fixed TICK_TIMEOUT hard kill) ──
# 2026-08-04: the old design force-killed every tick at a fixed 25 min, which
# butchered legitimately-long investigations mid-work (rc=143, "did nothing").
# Instead of a fixed cap we now watch for PROGRESS. The claude session runs in
# streaming mode, so its log file grows with every step it takes (each tool
# call and message is a "check-in"). The watchdog samples the log every
# PROGRESS_INTERVAL seconds; a tick is only killed if it makes NO progress
# (log stops growing entirely) for STALL_MAX_MISSES consecutive samples —
# i.e. a genuine hang, not slow-but-working. A long build or a slow SSH is
# fine as long as SOMETHING keeps happening within the window.
PROGRESS_INTERVAL="${PROGRESS_INTERVAL:-300}"   # sample every 5 min
STALL_MAX_MISSES="${STALL_MAX_MISSES:-4}"        # kill after 4 empty samples (= 20 min of total silence)
# Absolute backstop so a pathological loop that keeps emitting output can't run
# forever and hold the lockfile indefinitely. Set very high; normal ticks never
# reach it. Set to 0 to disable entirely.
MAX_WALL="${MAX_WALL:-7200}"                     # 2 h hard ceiling (safety only)

run_ticker() {
    local name="$1"
    local prompt_file="$2"
    local hist="/tmp/cw-ticker-${name}.history"
    local log="/tmp/cw-ticker-${name}.$(date '+%Y%m%d').log"

    if [[ ! -f "$prompt_file" ]]; then
        echo "[$(date '+%F %T')] SKIP   ticker=${name} (no prompt file)" >> "$hist"
        return 0
    fi

    echo "[$(date '+%F %T')] FIRED  ticker=${name}" >> "$hist"
    echo "===== [$(date '+%F %T')] ${name} tick start (progress watchdog: sample ${PROGRESS_INTERVAL}s, stall after ${STALL_MAX_MISSES} misses) =====" >> "$log"

    cd "$CW/ticker-workdir" || { echo "[$(date '+%F %T')] ABORT  cd failed" >> "$hist"; return 1; }

    # Stream events to a live progress file so the watchdog can SEE progress.
    # --output-format stream-json --verbose emits one JSON line per step (tool
    # call, message, result), so this file grows continuously while the session
    # is actually doing anything. The human-readable summary is still appended
    # to $log at the end.
    local stream="/tmp/cw-ticker-${name}.stream.jsonl"

    # Model: claude-sonnet-5 (owner requested Sonnet, 2026-08-11). Use the
    # explicit id, NOT a bare alias: on the Bedrock/SF gateway "opus"/older
    # sonnet ids 401 ("Team not allowed to access model"). Verified accessible:
    # claude-sonnet-5 OK; claude-sonnet-4-5 is 401-blocked; claude-opus-4-8 OK.
    #
    # --strict-mcp-config: start with NO filesystem MCP servers for the tick (the
    # Salesforce Org62 connector hangs in the headless launchd context, and the
    # ticker needs zero Salesforce access). < /dev/null: never block waiting on
    # stdin under launchd.
    #
    # STARTUP-RETRY (2026-08-11): intermittently a launchd-spawned claude
    # deadlocks on an INTERNAL startup mutex before it ever emits its init line —
    # traced live: main thread parked in __ulock_wait with ZERO network sockets,
    # so it is NOT the API/MCP, just a flaky startup race. A freshly-launched
    # claude is healthy. So instead of letting the 20-min progress watchdog burn
    # a whole tick on a corpse (which is exactly why the ticker "did nothing"), we
    # watch for the FIRST byte of output within STARTUP_GRACE and, if none comes,
    # kill and RELAUNCH — up to STARTUP_RETRIES times. This self-heals the race.
    local STARTUP_GRACE="${STARTUP_GRACE:-90}"
    local STARTUP_RETRIES="${STARTUP_RETRIES:-3}"

    local CPID="" attempt=0
    while : ; do
        attempt=$(( attempt + 1 ))
        : > "$stream"
        "$CLAUDE" -p "Read the file ${prompt_file} and follow its instructions exactly. Do all work described there." \
            --permission-mode bypassPermissions \
            --model claude-sonnet-5 \
            --strict-mcp-config \
            --output-format stream-json --verbose \
            < /dev/null >> "$stream" 2>&1 &
        CPID=$!

        # Wait for the first output (init line) within the grace window.
        local waited=0 started=0 sz=0
        while [[ "$waited" -lt "$STARTUP_GRACE" ]]; do
            sleep 5; waited=$(( waited + 5 ))
            if ! kill -0 "$CPID" 2>/dev/null; then started=1; break; fi   # exited fast; let wait handle rc
            sz=$(wc -c < "$stream" 2>/dev/null | tr -d ' '); [[ -z "$sz" ]] && sz=0
            if [[ "$sz" -gt 0 ]]; then started=1; break; fi
        done
        [[ "$started" -eq 1 ]] && break

        echo "[$(date '+%F %T')] STARTUP-HANG ticker=${name} attempt=${attempt}/${STARTUP_RETRIES} pid=${CPID} — no output in ${STARTUP_GRACE}s; relaunching" >> "$hist"
        pkill -TERM -P "$CPID" 2>/dev/null; kill -TERM "$CPID" 2>/dev/null; sleep 3
        pkill -KILL -P "$CPID" 2>/dev/null; kill -KILL "$CPID" 2>/dev/null
        if [[ "$attempt" -ge "$STARTUP_RETRIES" ]]; then
            echo "[$(date '+%F %T')] STARTUP-FAIL ticker=${name} — ${STARTUP_RETRIES} silent starts; skipping this tick" >> "$hist"
            echo "[$(date '+%F %T')] ${name}: claude failed to start ${STARTUP_RETRIES}x (startup deadlock, no output); tick skipped, will retry next cycle." >> /tmp/cw-ticker-alerts.txt
            return 1
        fi
        sleep 5
    done

    # Progress watchdog: kill ONLY on a genuine stall (no new output for
    # STALL_MAX_MISSES consecutive samples). Slow-but-working ticks are fine.
    (
        local misses=0
        local last_size=-1
        local elapsed=0
        while kill -0 "$CPID" 2>/dev/null; do
            sleep "$PROGRESS_INTERVAL"
            elapsed=$(( elapsed + PROGRESS_INTERVAL ))
            local size
            size=$(wc -c < "$stream" 2>/dev/null | tr -d ' ')
            [[ -z "$size" ]] && size=0
            if [[ "$size" -gt "$last_size" ]]; then
                # Progress made since last sample — reset the stall counter.
                misses=0
                last_size="$size"
                echo "[$(date '+%F %T')] PROGRESS ticker=${name} bytes=${size} (elapsed ${elapsed}s)" >> "$hist"
            else
                misses=$(( misses + 1 ))
                echo "[$(date '+%F %T')] NO-PROGRESS ticker=${name} miss ${misses}/${STALL_MAX_MISSES} (bytes=${size}, elapsed ${elapsed}s)" >> "$hist"
                if [[ "$misses" -ge "$STALL_MAX_MISSES" ]]; then
                    echo "[$(date '+%F %T')] STALL-KILL ticker=${name} pid=${CPID} — no progress for $(( STALL_MAX_MISSES * PROGRESS_INTERVAL ))s" >> "$hist"
                    echo "===== [$(date '+%F %T')] ${name} STALL-KILL (no progress) =====" >> "$log"
                    pkill -TERM -P "$CPID" 2>/dev/null; kill -TERM "$CPID" 2>/dev/null
                    sleep 10
                    pkill -KILL -P "$CPID" 2>/dev/null; kill -KILL "$CPID" 2>/dev/null
                    break
                fi
            fi
            # Absolute safety backstop (0 = disabled).
            if [[ "$MAX_WALL" -gt 0 && "$elapsed" -ge "$MAX_WALL" ]]; then
                echo "[$(date '+%F %T')] MAX-WALL-KILL ticker=${name} pid=${CPID} — hit ${MAX_WALL}s ceiling" >> "$hist"
                echo "===== [$(date '+%F %T')] ${name} MAX-WALL-KILL =====" >> "$log"
                pkill -TERM -P "$CPID" 2>/dev/null; kill -TERM "$CPID" 2>/dev/null
                sleep 10
                pkill -KILL -P "$CPID" 2>/dev/null; kill -KILL "$CPID" 2>/dev/null
                break
            fi
        done
    ) &
    local WDPID=$!

    wait "$CPID"
    local RC=$?

    kill "$WDPID" 2>/dev/null
    wait "$WDPID" 2>/dev/null

    # Fold the streamed session into the human-readable log for later reading.
    cat "$stream" >> "$log" 2>/dev/null

    echo "===== [$(date '+%F %T')] ${name} tick done rc=${RC} =====" >> "$log"
    echo "[$(date '+%F %T')] DONE   ticker=${name} rc=${RC}" >> "$hist"

    return $RC
}

echo "[$(date '+%F %T')] UNIFIED ticker run START" >> /tmp/cw-ticker-unified.history

# Run in priority order: master first, then homebrews, then FBE
run_ticker "master" \
    "$TOOLS/tickers/prompt-master.txt"

run_ticker "homebrews" \
    "$TOOLS/tickers/prompt-homebrews.txt"

run_ticker "fbe-tasks" \
    "$TOOLS/tickers/prompt-fbe-tasks.txt"

echo "[$(date '+%F %T')] UNIFIED ticker run DONE" >> /tmp/cw-ticker-unified.history
