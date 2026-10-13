#!/bin/zsh
# Designer Request Bridge (2026-10-13)
# Bridges designer requests (bug/build/extract/update) to admin queue for unified processing
# Run every 2 minutes via launchd or cron

set -u
SSH=(ssh -i /Users/gremus/.ssh/oracle_cw_ed25519 -o ConnectTimeout=10 oracle-cw-server@cwo.freeddns.org)
PROCESSED="/tmp/cw-designer-requests-processed.log"
touch "$PROCESSED"

# Get pending requests from designer
pending=$("${SSH[@]}" "python3 <<'EOF'
import json
from pathlib import Path

data_file = Path('/opt/cwo/designer/data/requests.json')
if not data_file.exists():
    exit(0)

data = json.loads(data_file.read_text())
requests = data if isinstance(data, list) else data.get('requests', [])

for req in requests:
    if req.get('status') in ('requested', 'open'):
        print(f\"{req['id']}|{req.get('type', 'unknown')}|{req.get('entityId', 'unknown')}|{req.get('text', req.get('description', '')[:200])}\")
EOF
" 2>/dev/null) || exit 0

if [[ -z "$pending" ]]; then
    exit 0
fi

# Process each pending request
echo "$pending" | while IFS='|' read -r req_id req_type entity_id text; do
    # Skip if already processed
    if grep -q "^$req_id\$" "$PROCESSED" 2>/dev/null; then
        continue
    fi

    # Map request type to admin queue format
    case "$req_type" in
        bug)
            prefix="FACTION-BUG"
            ;;
        build)
            prefix="FACTION-BUILD"
            ;;
        extract)
            prefix="MAP-EXTRACT"
            ;;
        update)
            prefix="FACTION-UPDATE"
            ;;
        answers)
            prefix="DESIGN-ANSWERS"
            ;;
        *)
            prefix="DESIGNER-REQUEST"
            ;;
    esac

    # Queue to admin console
    "${SSH[@]}" "printf '[%s] $prefix $req_id: %s\n' \"\$(date '+%F %T')\" \"$text\" >> /tmp/claude-prompts.log" 2>/dev/null

    if [[ $? -eq 0 ]]; then
        echo "$req_id" >> "$PROCESSED"
        echo "[$(date '+%F %T')] Bridged $req_id ($req_type) to admin queue"
    fi
done
