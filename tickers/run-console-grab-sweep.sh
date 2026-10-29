#!/bin/zsh
# Console-grab SWEEP ticker.
#
# Fires hourly (via its plist). Runs tools/console-grab.py --sweep, which loads
# every active (non-bot, not-completed) game in headless Chromium LOCALLY and
# writes the captured console errors into each game's annotation Notes, flagging
# games with uncaught errors as broken.
#
# Plain shell + python — spends no AI session.
#
# Explicit env: launchd does not source the shell profile, so the Salesforce CA
# bundle and PATH must be set here for curl/python/Chromium to work.

set -u

export HOME="/Users/gremus"
export NODE_EXTRA_CA_CERTS="/Users/gremus/.claude/certs/salesforce-ca-bundle.pem"
export PATH="/Users/gremus/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

TOOLS="/Users/gremus/Claude-Projects/cthulhu-wars-tools"
RUNNER="${TOOLS}/tools/console-grab.py"

HIST="/tmp/cw-console-grab-sweep.history"
LOG="/tmp/cw-console-grab-sweep.$(date '+%Y%m%d').log"

echo "===== [$(date '+%F %T')] console-grab sweep start =====" >> "$LOG"
echo "[$(date '+%F %T')] FIRED  console-grab sweep" >> "$HIST"

python3 "$RUNNER" --sweep >> "$LOG" 2>&1
RC=$?

echo "===== [$(date '+%F %T')] console-grab sweep done rc=${RC} =====" >> "$LOG"
echo "[$(date '+%F %T')] DONE   console-grab sweep rc=${RC}" >> "$HIST"
exit "$RC"
