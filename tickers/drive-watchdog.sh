#!/bin/zsh
# ---------------------------------------------------------------------------
# Google Drive File Stream watchdog  (CONSERVATIVE v2, 2026-08-30)
#
# Purpose: Google Drive's File Provider service can WEDGE on macOS — every read
# of a Drive file returns `[Errno 11] Resource deadlock avoided` (EDEADLK) even
# though the file is fully local. A genuine stuck wedge is cleared only by a full
# Drive restart (quit + kill File Provider/Finder extensions + relaunch). When it
# happens the CW ticker can't read `master current tasks.xlsx` and stalls.
#
# ⚠ HARD-LEARNED LESSON (2026-08-30): restarting Google Drive TOO OFTEN is worse
# than the disease. Every restart tears down + rebuilds the File Provider mount,
# which itself briefly deadlocks the already-running ticker → that produces a
# fresh EDEADLK alert → a naive watchdog restarts again → self-sustaining outage.
# The first version of this watchdog (restart on first alert, 6-min cooldown)
# turned a transient blip into an 8-hour outage. So this version is deliberately
# SLOW and SKEPTICAL:
#   * It only restarts when a wedge has persisted CONTINUOUSLY for >= PERSIST_MIN
#     (a transient/self-inflicted blip clears on its own well before that).
#   * It waits >= COOLDOWN_MIN between restarts (a restart gets several tick
#     windows to settle before we'd ever touch Drive again).
#   * It restarts at most MAX_RESTARTS times per outage, then GIVES UP and posts a
#     desktop notification for manual attention instead of looping.
#   * When the newest ticker alert is NOT a wedge, the outage is considered over
#     and all counters reset.
#
# Detection is permission-safe: a launchd agent has no Full Disk Access to
# ~/Library/CloudStorage (a direct read returns EPERM and would false-trigger),
# so we NEVER read the Drive file. We parse the ticker's alert log in /tmp
# (world-readable, written by the ticker which DOES have access).
#
# Install:   launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.gremus.cw-drive-watchdog.plist
# Uninstall: launchctl bootout   gui/$(id -u)/com.gremus.cw-drive-watchdog
# ---------------------------------------------------------------------------

set -u

ALERTS="/tmp/cw-ticker-alerts.txt"
LOG="/tmp/cw-drive-watchdog.log"
LASTSTART_STATE="/tmp/cw-drive-watchdog.laststart"   # epoch of last Drive restart
COUNT_STATE="/tmp/cw-drive-watchdog.restarts"        # restarts in the current outage

PERSIST_MIN=40        # wedge must persist continuously this long before 1st restart
COOLDOWN_MIN=90       # minimum minutes between restarts
MAX_RESTARTS=2        # per outage, then give up + notify
POST_RESTART_WAIT=35  # wait for Drive after relaunch

log() { print -r -- "[$(date '+%Y-%m-%d %H:%M:%S %Z')] $*" >> "$LOG"; }

# --- how long has the ticker been CONTINUOUSLY wedged? -----------------------
# Prints an integer: minutes the newest unbroken run of wedge alerts has lasted,
# or 0 if the newest ticker alert is NOT a wedge (outage considered over/none).
# Parses /tmp only — no Drive access needed.
wedge_minutes() {
  /usr/bin/python3 - "$ALERTS" <<'PY'
import sys, re, datetime
path = sys.argv[1]
try:
    with open(path, 'r', errors='replace') as f:
        lines = f.readlines()
except OSError:
    print(0); sys.exit(0)

# Only lines that are a ticker status alert (start with a bracketed timestamp and
# name one of the three tickers) count as "relevant". Among those, a wedge line
# matches WEDGE. We walk relevant lines newest->oldest; if the newest relevant
# line is a wedge, measure back to the start of the unbroken wedge streak.
TS = re.compile(r'^\[(\d{4}-\d{2}-\d{2})[ T](\d{2}):(\d{2})(?::(\d{2}))?')
RELEVANT = re.compile(r'\b(MASTER|HOMEBREWS|FBE)\b')
WEDGE = re.compile(r'Resource deadlock avoided|Errno 11|dataless|materialize fail|Drive[- ]busy|Drive outage|mount error|mount (?:still )?unresponsive|Interrupted system call|ongoing outage|Outage persisting|chronic (?:per-file )?lock|hung with zero output', re.I)

def ts_of(line):
    m = TS.match(line)
    if not m: return None
    y,mo,d = map(int, m.group(1).split('-'))
    hh = int(m.group(2)); mm = int(m.group(3)); ss = int(m.group(4) or 0)
    try: return datetime.datetime(y,mo,d,hh,mm,ss)
    except ValueError: return None

relevant = [(ts_of(l), l) for l in lines]
relevant = [(t,l) for (t,l) in relevant if t is not None and RELEVANT.search(l)]
if not relevant:
    print(0); sys.exit(0)

newest_ts, newest_line = relevant[-1]
if not WEDGE.search(newest_line):
    print(0); sys.exit(0)   # newest relevant alert is clean → not currently wedged

# Walk backwards while alerts remain wedge-type; find start of the streak.
streak_start = newest_ts
for t, l in reversed(relevant):
    if WEDGE.search(l):
        streak_start = t
    else:
        break

# Age of the streak, measured against the NEWEST alert (robust to a stale clock
# and to the watchdog running slightly after the last tick).
delta = (newest_ts - streak_start).total_seconds()
# Require the wedge to be *current*. A genuine ongoing wedge re-alerts every
# tick (~15m); if the newest wedge alert is older than one-and-a-bit tick
# intervals, at least one tick has passed WITHOUT wedging → the ticker recovered
# and this is history. Erring toward "recovered" is intentional: after the
# 2026-08-30 restart-loop incident we prefer to under-restart, never over-restart
# (a still-genuine wedge will re-arm us within the next tick anyway).
STALE_MIN = 22
now = datetime.datetime.now()
if (now - newest_ts).total_seconds() > STALE_MIN*60:
    print(0); sys.exit(0)
print(int(delta // 60))
PY
}

notify() {
  osascript -e "display notification \"$1\" with title \"CW Drive Watchdog\"" >/dev/null 2>&1 || true
}

restart_drive() {
  log "RESTARTING Google Drive..."
  osascript -e 'tell application "Google Drive" to quit' >/dev/null 2>&1
  sleep 6
  pkill -f "Google Drive.app/Contents/MacOS/Google Drive" 2>/dev/null
  pkill -9 -f "DFSFileProviderExtension" 2>/dev/null
  pkill -9 -f "FinderSyncExtension" 2>/dev/null
  sleep 4
  open -a "Google Drive"
  print -r -- "$(date +%s)" > "$LASTSTART_STATE"
  log "relaunched Google Drive; waiting ${POST_RESTART_WAIT}s. Leaving it ALONE for >=${COOLDOWN_MIN}m so it can settle."
  sleep "$POST_RESTART_WAIT"
}

# --- main --------------------------------------------------------------------
WM=$(wedge_minutes 2>/dev/null); WM=${WM:-0}

# Not currently wedged → outage (if any) is over. Reset counters, stay quiet.
if (( WM == 0 )); then
  [[ -f "$COUNT_STATE" ]] && { rm -f "$COUNT_STATE"; log "wedge cleared — reset restart counter."; }
  exit 0
fi

# Wedged, but not long enough yet → likely transient/self-inflicted; wait it out.
if (( WM < PERSIST_MIN )); then
  exit 0
fi

# Persisted long enough. Respect cooldown so a restart can actually settle.
now=$(date +%s); last=0
[[ -f "$LASTSTART_STATE" ]] && last=$(cat "$LASTSTART_STATE" 2>/dev/null || echo 0)
if (( now - last < COOLDOWN_MIN*60 )); then
  log "wedged ${WM}m but within ${COOLDOWN_MIN}m cooldown ($(((now-last)/60))m since last restart) — waiting."
  exit 0
fi

count=0; [[ -f "$COUNT_STATE" ]] && count=$(cat "$COUNT_STATE" 2>/dev/null || echo 0)
if (( count >= MAX_RESTARTS )); then
  log "GIVING UP: wedged ${WM}m and ${count} restart(s) already didn't fix it. This is NOT the transient wedge — likely a genuine Drive/account/network problem. Manual attention needed. (Won't restart again until a clean tick resets me.)"
  notify "Ticker Drive still wedged after ${count} restarts — needs manual attention."
  exit 0
fi

log "GENUINE STUCK WEDGE: continuously wedged ${WM}m (>=${PERSIST_MIN}m), ${count} prior restart(s) this outage. Restarting Drive."
restart_drive
print -r -- "$((count + 1))" > "$COUNT_STATE"
log "restart #$((count+1)) done. Next tick should confirm reads recover."
exit 0
