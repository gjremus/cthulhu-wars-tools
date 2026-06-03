#!/bin/bash
# Deploy admin.html to the live VM. The admin tool is served by the akka-http
# backend (cwo.service) which reads it from /opt/cwo/solo/admin.html.
#
# Usage:
#   ./deploy-admin-to-vm.sh
#
# Pattern lifted from the 2026-06-03 14:20 manual deploy that should have been
# scripted earlier (admin.html TT+BB cards landed in repo at 12:00 but didn't
# reach prod because no script existed; user caught it 2h later).

set -euo pipefail

REPO_ROOT="/Users/gremus/claude-projects/cthulhu-wars-tools"
ADMIN_HTML="$REPO_ROOT/admin/admin.html"
SSH_KEY="/Users/gremus/My Drive/Personal/Games/Cthulhu Wars/Library at Celaeno/Server Deployment/oracle_cw_ed25519"
HOST="oracle-cw-server@35.255.125.91"
REMOTE_PATH="/opt/cwo/solo/admin.html"

if [ ! -f "$ADMIN_HTML" ]; then
    echo "ERROR: $ADMIN_HTML missing."
    exit 1
fi
if [ ! -f "$SSH_KEY" ]; then
    echo "ERROR: ssh key not found at: $SSH_KEY"
    exit 1
fi

STAMP="$(date +%Y%m%d-%H%M%S)"

echo "==> [backup] /opt/cwo/solo/admin.html → admin.html.bak-$STAMP"
ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$HOST" \
    "cp $REMOTE_PATH ${REMOTE_PATH}.bak-$STAMP" 2>&1 | tail -3

echo "==> [upload] $ADMIN_HTML → $REMOTE_PATH"
scp -i "$SSH_KEY" -o StrictHostKeyChecking=no -C "$ADMIN_HTML" "$HOST:$REMOTE_PATH" 2>&1 | tail -3

echo "==> [verify] HEAD https://cwo.freeddns.org/admin.html"
curl -s -o /dev/null -w "  HTTP %{http_code}  size_bytes=%{size_download}\n" "https://cwo.freeddns.org/admin.html"

echo
echo "Done.  Live: https://cwo.freeddns.org/admin.html"
