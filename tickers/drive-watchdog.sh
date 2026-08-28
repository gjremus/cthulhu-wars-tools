#!/bin/zsh
# ---------------------------------------------------------------------------
# Google Drive File Stream watchdog.
#
# Problem it solves: Google Drive's File Provider service periodically WEDGES on
# macOS. Once wedged, every non-interactive read of a Drive file returns
# `[Errno 11] Resource deadlock avoided` (EDEADLK) even though the file is fully
# local. Google Drive's own auto-restart does NOT clear this state. The only
# reliable fix is a full quit + kill of the File Provider/Finder extensions +
# relaunch. When this happens the CW ticker cannot read `master current
# tasks.xlsx` and silently stalls for hours/days (observed for ~weeks in Aug 2026).
#
# This watchdog runs from a gui/$UID LaunchAgent (same session as the ticker, so
# File Provider access matches the ticker's) every few minutes. It tries to read
# a canary Drive file with a hard timeout. If the read deadlocks / times out /
# returns a non-materialized stub, it restarts Google Drive and re-verifies.
#
# It is rate-limited: it will not restart Drive more than once per COOLDOWN
# seconds, so a genuinely offline account can't cause a restart storm.
#
# Install:   launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.gremus.cw-drive-watchdog.plist
# Uninstall: launchctl bootout   gui/$(id -u)/com.gremus.cw-drive-watchdog
# ---------------------------------------------------------------------------

set -u

CANARY="/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars/master current tasks.xlsx"
LOG="/tmp/cw-drive-watchdog.log"
STATE="/tmp/cw-drive-watchdog.laststart"   # epoch seconds of last Drive restart
READ_TIMEOUT=25                            # seconds to allow a canary read
COOLDOWN=360                               # min seconds between Drive restarts
POST_RESTART_WAIT=30                       # seconds to wait for Drive to come back

log() { print -r -- "[$(date '+%Y-%m-%d %H:%M:%S %Z')] $*" >> "$LOG"; }

# --- read the canary with a hard watchdog -----------------------------------
# Returns 0 = healthy (full PK/zip read), 1 = wedged (EDEADLK / timeout / stub).
check_canary() {
  local out="/tmp/cw-drive-watchdog.readout"
  local err="/tmp/cw-drive-watchdog.readerr"
  : > "$err"
  # Full read in a subshell; a small peek does NOT trigger Drive's fetch, so we
  # read the whole file — same technique the ticker's _materialize_or_die uses.
  ( /usr/bin/python3 - "$CANARY" > "$out" 2> "$err" <<'PY'
import sys
with open(sys.argv[1], 'rb') as fh:
    data = fh.read()
# a valid .xlsx is a PK zip; a dataless stub reads short/empty
sys.exit(0 if len(data) >= 4 and data[:2] == b'PK' else 3)
PY
  ) &
  local pid=$!
  local waited=0
  while kill -0 "$pid" 2>/dev/null; do
    if (( waited >= READ_TIMEOUT )); then
      kill -9 "$pid" 2>/dev/null
      log "CANARY READ TIMED OUT after ${READ_TIMEOUT}s (Drive wedged / hung fetch)"
      return 1
    fi
    sleep 1
    (( waited++ ))
  done
  wait "$pid"; local rc=$?
  if (( rc == 0 )); then
    return 0
  fi
  local msg="$(tr -d '\0' < "$err" 2>/dev/null | tail -1)"
  log "CANARY READ FAILED (rc=$rc): ${msg:-non-materialized stub / short read}"
  return 1
}

# --- restart Google Drive ----------------------------------------------------
restart_drive() {
  log "RESTARTING Google Drive..."
  osascript -e 'tell application "Google Drive" to quit' >/dev/null 2>&1
  sleep 6
  # Kill the main app + the File Provider / Finder extensions that actually hold
  # the wedge (the app's own auto-restart leaves these stuck).
  pkill -f "Google Drive.app/Contents/MacOS/Google Drive" 2>/dev/null
  pkill -9 -f "DFSFileProviderExtension" 2>/dev/null
  pkill -9 -f "FinderSyncExtension" 2>/dev/null
  sleep 4
  open -a "Google Drive"
  print -r -- "$(date +%s)" > "$STATE"
  log "relaunched Google Drive; waiting ${POST_RESTART_WAIT}s for File Provider..."
  sleep "$POST_RESTART_WAIT"
}

# --- main --------------------------------------------------------------------
if check_canary; then
  # healthy — stay quiet (log at most a heartbeat is unnecessary/noisy)
  exit 0
fi

# Wedged. Respect cooldown so we never storm-restart.
now=$(date +%s)
last=0
[[ -f "$STATE" ]] && last=$(cat "$STATE" 2>/dev/null || echo 0)
if (( now - last < COOLDOWN )); then
  log "WEDGED but within cooldown ($(( now - last ))s < ${COOLDOWN}s since last restart) — skipping"
  exit 0
fi

restart_drive

# Re-verify. Log the outcome either way so a persistent failure is visible.
if check_canary; then
  log "RECOVERED: canary reads cleanly after Drive restart."
else
  log "STILL WEDGED after restart — likely a genuine Drive/account/network issue, not the transient deadlock. Manual attention may be needed."
fi
exit 0
