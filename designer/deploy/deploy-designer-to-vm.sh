#!/bin/bash
# Deploy CW Faction Designer to the VM.
# Uploads www/ and server/, restarts service, verifies deployment.
# NEVER touches data/.

set -euo pipefail

SSH_KEY="$HOME/.ssh/oracle_cw_ed25519"
SSH_OPTS="-o ConnectTimeout=15 -o StrictHostKeyChecking=no"
HOST="oracle-cw-server@cwo.freeddns.org"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

if [ ! -f "$SSH_KEY" ]; then
    echo "ERROR: SSH key not found at $SSH_KEY" >&2
    exit 1
fi

if [ ! -d "$PROJECT_DIR/www" ] || [ ! -f "$PROJECT_DIR/server/designer_server.py" ]; then
    echo "ERROR: Required directories/files not found in $PROJECT_DIR" >&2
    exit 1
fi

echo "==> Uploading www/ ..."
rsync -avz --delete -e "ssh -i $SSH_KEY $SSH_OPTS" \
    "$PROJECT_DIR/www/" \
    "$HOST:/opt/cwo/designer/www/"

echo "==> Uploading server/designer_server.py ..."
scp -i "$SSH_KEY" $SSH_OPTS \
    "$PROJECT_DIR/server/designer_server.py" \
    "$HOST:/opt/cwo/designer/server/designer_server.py"

echo "==> Setting permissions..."
ssh -i "$SSH_KEY" $SSH_OPTS "$HOST" bash <<'REMOTE_PERMS'
chmod 644 /opt/cwo/designer/server/designer_server.py
find /opt/cwo/designer/www -type f -exec chmod 644 {} \;
find /opt/cwo/designer/www -type d -exec chmod 755 {} \;
REMOTE_PERMS

echo "==> Restarting cwo-designer service..."
ssh -i "$SSH_KEY" $SSH_OPTS "$HOST" "sudo systemctl restart cwo-designer"

sleep 2

echo "==> Verifying health endpoint..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "https://cwo.freeddns.org/designer/api/health")
if [ "$HTTP_CODE" != "200" ]; then
    echo "ERROR: Health check failed (HTTP $HTTP_CODE)" >&2
    exit 1
fi
echo "  Health check: OK (HTTP 200)"

echo "==> Verifying index.html..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "https://cwo.freeddns.org/designer/")
if [ "$HTTP_CODE" != "200" ]; then
    echo "ERROR: index.html check failed (HTTP $HTTP_CODE)" >&2
    exit 1
fi
echo "  index.html: OK (HTTP 200)"

# Compare index.html hashes
if [ -f "$PROJECT_DIR/www/index.html" ]; then
    LOCAL_MD5=$(md5 -q "$PROJECT_DIR/www/index.html" 2>/dev/null || md5sum "$PROJECT_DIR/www/index.html" | cut -d' ' -f1)
    REMOTE_MD5=$(ssh -i "$SSH_KEY" $SSH_OPTS "$HOST" "md5sum /opt/cwo/designer/www/index.html 2>/dev/null | cut -d' ' -f1")
    echo "  Local index.html:  $LOCAL_MD5"
    echo "  Remote index.html: $REMOTE_MD5"
    if [ "$LOCAL_MD5" != "$REMOTE_MD5" ]; then
        echo "  WARNING: MD5 mismatch (may be due to line endings or rsync timing)"
    fi
fi

echo "==> Checking memory usage..."
MEMORY=$(ssh -i "$SSH_KEY" $SSH_OPTS "$HOST" "sudo systemctl show cwo-designer -p MemoryCurrent --value")
echo "  MemoryCurrent: $MEMORY bytes"

echo
echo "Deployment complete."
echo "Live at: https://cwo.freeddns.org/designer/"
