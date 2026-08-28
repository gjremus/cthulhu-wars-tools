#!/bin/zsh
# ---------------------------------------------------------------------------
# Google Drive File Stream watchdog.
#
# Problem it solves: Google Drive's File Provider service periodically WEDGES on
# macOS. Once wedged, every read of a Drive file returns
# `[Errno 11] Resource deadlock avoided` (EDEADLK) even though the file is fully
# local. Google Drive's own auto-restart does NOT clear this state; only a full
# quit + kill of the File Provider/Finder extensions + relaunch does. When it
# happens the CW ticker cannot read `master current tasks.xlsx` and silently
# stalls for hours/days (observed ~weeks in Aug 2026).
#
# DETECTION (important): this agent runs under launchd and does NOT have Full
# Disk Access to ~/Library/CloudStorage (TCC blocks it with EPERM), so it CANNOT
# read the Drive file itself to probe. Instead it watches the CW ticker's alert
# log in /tmp — the ticker DOES have access (it runs through `claude`, which has
# Full Disk Access) and it writes the real EDEADLK/dataless signature there on
# every wedged tick. We react only to NEW alert lines (tracked by byte offset),
# so a single wedge triggers exactly one restart, not a loop.
#
# Install:   launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.gremus.cw-drive-watchdog.plist
# Uninstall: launchctl bootout   gui/$(id -u)/com.gremus.cw-drive-watchdog
# ---------------------------------------------------------------------------

set -u

ALERTS="/tmp/cw-ticker-alerts.txt"
LOG="/tmp/cw-drive-watchdog.log"
OFFSET_STATE="/tmp/cw-drive-watchdog.offset"     # last alert-file byte offset seen
LASTSTART_STATE="/tmp/cw-drive-watchdog.laststart"  # epoch of last Drive restart
COOLDOWN=360                                      # min seconds between restarts
POST_RESTART_WAIT=30                              # wait for Drive after relaunch

# Signature of a genuine, fresh Drive wedge in the ticker's alerts. EDEADLK is
# the definitive one; the dataless/materialize phrases only count when paired
# with the ticker's own "STILL dataless / fresh ... failure this tick" wording,
# which the ticker emits only after a real failed materialize (not stale flags).
SIG='Resource deadlock avoided|Errno 11|STILL dataless|materialize failure this tick'

log() { print -r -- "[$(date '+%Y-%m-%d %H:%M:%S %Z')] $*" >> "$LOG"; }

# --- read only the alert-file bytes appended since our last run --------------
new_alert_text() {
  [[ -f "$ALERTS" ]] || { print -n ""; return; }
  local size prev
  size=$(wc -c < "$ALERTS" 2>/dev/null | tr -d ' ')
  prev=0; [[ -f "$OFFSET_STATE" ]] && prev=$(cat "$OFFSET_STATE" 2>/dev/null || echo 0)
  # If the file shrank/rotated (offset > size), start from the top.
  (( prev > size )) && prev=0
  # Emit the new tail, then advance the offset for next time.
  if (( size > prev )); then
    tail -c +$((prev + 1)) "$ALERTS" 2>/dev/null
  fi
  print -r -- "$size" > "$OFFSET_STATE"
}

restart_drive() {
  log "RESTARTING Google Drive (fresh wedge signature in ticker alerts)..."
  osascript -e 'tell application "Google Drive" to quit' >/dev/null 2>&1
  sleep 6
  pkill -f "Google Drive.app/Contents/MacOS/Google Drive" 2>/dev/null
  pkill -9 -f "DFSFileProviderExtension" 2>/dev/null
  pkill -9 -f "FinderSyncExtension" 2>/dev/null
  sleep 4
  open -a "Google Drive"
  print -r -- "$(date +%s)" > "$LASTSTART_STATE"
  log "relaunched Google Drive; waiting ${POST_RESTART_WAIT}s for File Provider..."
  sleep "$POST_RESTART_WAIT"
  log "Google Drive back up. Next ticker tick will confirm reads succeed."
}

# --- main --------------------------------------------------------------------
NEW="$(new_alert_text)"

# No new alert text, or none of it matches the wedge signature → healthy/quiet.
if [[ -z "$NEW" ]] || ! print -r -- "$NEW" | grep -qE "$SIG"; then
  exit 0
fi

# Fresh wedge detected. Respect cooldown so we never storm-restart.
HIT="$(print -r -- "$NEW" | grep -E "$SIG" | tail -1 | cut -c1-160)"
now=$(date +%s); last=0
[[ -f "$LASTSTART_STATE" ]] && last=$(cat "$LASTSTART_STATE" 2>/dev/null || echo 0)
if (( now - last < COOLDOWN )); then
  log "WEDGE signature seen but within cooldown ($(( now - last ))s < ${COOLDOWN}s) — skipping. [$HIT]"
  exit 0
fi

log "WEDGE detected in ticker alerts: $HIT"
restart_drive
exit 0
