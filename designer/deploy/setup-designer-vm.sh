#!/bin/bash
# Idempotent setup script for CW Faction Designer on the VM.
# Run from Mac: ./setup-designer-vm.sh

set -euo pipefail

SSH_KEY="$HOME/.ssh/oracle_cw_ed25519"
SSH_OPTS="-o ConnectTimeout=15 -o StrictHostKeyChecking=no"
HOST="oracle-cw-server@cwo.freeddns.org"

TOKEN_FILE="$HOME/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars/Maps/Library at Celaeno/Server Deployment/owner-admin-token.txt"

if [ ! -f "$SSH_KEY" ]; then
    echo "ERROR: SSH key not found at $SSH_KEY" >&2
    exit 1
fi

if [ ! -f "$TOKEN_FILE" ]; then
    echo "ERROR: Admin token file not found at $TOKEN_FILE" >&2
    exit 1
fi

echo "==> Reading admin token..."
ADMIN_TOKEN=$(cat "$TOKEN_FILE" | tr -d '[:space:]')
if [ -z "$ADMIN_TOKEN" ]; then
    echo "ERROR: Admin token is empty" >&2
    exit 1
fi

# Hash the token
TOKEN_HASH=$(echo -n "$ADMIN_TOKEN" | shasum -a 256 | cut -d' ' -f1)

echo "==> Creating directory structure..."
ssh -i "$SSH_KEY" $SSH_OPTS "$HOST" bash <<'REMOTE_SETUP'
set -euo pipefail

sudo mkdir -p /opt/cwo/designer/{www,data,server}
sudo chown -R oracle-cw-server:oracle-cw-server /opt/cwo/designer
chmod 755 /opt/cwo/designer
chmod 755 /opt/cwo/designer/{www,data,server}
REMOTE_SETUP

echo "==> Writing admin token hash to VM..."
ssh -i "$SSH_KEY" $SSH_OPTS "$HOST" "echo '$TOKEN_HASH' > /opt/cwo/designer/admin-token.sha256"

echo "==> Installing systemd service..."
ssh -i "$SSH_KEY" $SSH_OPTS "$HOST" sudo tee /etc/systemd/system/cwo-designer.service > /dev/null <<'SERVICE_UNIT'
[Unit]
Description=CW Faction Designer Server
After=network.target

[Service]
Type=simple
User=oracle-cw-server
WorkingDirectory=/opt/cwo/designer
ExecStart=/usr/bin/python3 /opt/cwo/designer/server/designer_server.py --data /opt/cwo/designer/data --port 8091 --host 127.0.0.1 --token-hash-file /opt/cwo/designer/admin-token.sha256 --reference /opt/cwo/designer/www/reference.json
Restart=on-failure
RestartSec=10s
MemoryMax=96M
Nice=5

StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
SERVICE_UNIT

echo "==> Enabling service..."
ssh -i "$SSH_KEY" $SSH_OPTS "$HOST" sudo systemctl daemon-reload
ssh -i "$SSH_KEY" $SSH_OPTS "$HOST" sudo systemctl enable cwo-designer

echo "==> Configuring Caddy..."

# Backup Caddyfile
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
echo "==> Backing up Caddyfile to Caddyfile.backup.$TIMESTAMP"
ssh -i "$SSH_KEY" $SSH_OPTS "$HOST" "sudo cp /etc/caddy/Caddyfile /etc/caddy/Caddyfile.backup.$TIMESTAMP"

# Check if designer routes already present
if ssh -i "$SSH_KEY" $SSH_OPTS "$HOST" "sudo grep -q '# ── Faction Designer ──' /etc/caddy/Caddyfile"; then
    echo "==> Caddy routes already present, skipping..."
else
    echo "==> Inserting Caddy routes..."

    # Download Caddyfile, modify locally, upload
    TMP_CADDY=$(mktemp)
    scp -i "$SSH_KEY" $SSH_OPTS "$HOST:/etc/caddy/Caddyfile" "$TMP_CADDY"

    # Insert routes before the final reverse_proxy line
    # Find the cwo.freeddns.org block and insert before the last reverse_proxy
    python3 <<EOF
import sys

with open('$TMP_CADDY', 'r') as f:
    lines = f.readlines()

# Find the last reverse_proxy localhost:8080 line
insert_idx = -1
for i in range(len(lines) - 1, -1, -1):
    if 'reverse_proxy localhost:8080' in lines[i] or 'reverse_proxy 127.0.0.1:8080' in lines[i]:
        insert_idx = i
        break

if insert_idx == -1:
    print("ERROR: Could not find reverse_proxy line", file=sys.stderr)
    sys.exit(1)

# Insert designer routes
designer_routes = """
	# ── Faction Designer ──
	redir /designer /designer/ 308

	handle /designer/api/* {
		reverse_proxy 127.0.0.1:8091
	}

	handle /designer/img/* {
		uri strip_prefix /designer/img
		root * /opt/cwo/designer/data/images
		header Cache-Control "public, max-age=31536000, immutable"
		file_server
	}

	handle /designer/* {
		uri strip_prefix /designer
		root * /opt/cwo/designer/www
		file_server
	}

"""

lines.insert(insert_idx, designer_routes)

with open('$TMP_CADDY', 'w') as f:
    f.writelines(lines)
EOF

    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to modify Caddyfile" >&2
        rm -f "$TMP_CADDY"
        exit 1
    fi

    # Upload modified Caddyfile
    scp -i "$SSH_KEY" $SSH_OPTS "$TMP_CADDY" "$HOST:/tmp/Caddyfile.new"
    rm -f "$TMP_CADDY"

    # Validate
    echo "==> Validating Caddyfile..."
    if ! ssh -i "$SSH_KEY" $SSH_OPTS "$HOST" "sudo caddy validate --config /tmp/Caddyfile.new"; then
        echo "ERROR: Caddyfile validation failed, restoring backup" >&2
        ssh -i "$SSH_KEY" $SSH_OPTS "$HOST" "sudo cp /etc/caddy/Caddyfile.backup.$TIMESTAMP /etc/caddy/Caddyfile"
        exit 1
    fi

    # Install and reload
    ssh -i "$SSH_KEY" $SSH_OPTS "$HOST" "sudo mv /tmp/Caddyfile.new /etc/caddy/Caddyfile"
    ssh -i "$SSH_KEY" $SSH_OPTS "$HOST" "sudo chmod 644 /etc/caddy/Caddyfile"

    echo "==> Reloading Caddy..."
    ssh -i "$SSH_KEY" $SSH_OPTS "$HOST" "sudo systemctl reload caddy"
fi

echo "==> Starting designer service..."
ssh -i "$SSH_KEY" $SSH_OPTS "$HOST" "sudo systemctl start cwo-designer || sudo systemctl restart cwo-designer"

sleep 2

echo "==> Checking service status..."
ssh -i "$SSH_KEY" $SSH_OPTS "$HOST" "sudo systemctl status cwo-designer --no-pager" || true

echo
echo "Setup complete."
echo "Test health endpoint: curl https://cwo.freeddns.org/designer/api/health"
