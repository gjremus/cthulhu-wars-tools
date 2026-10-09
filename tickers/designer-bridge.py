#!/usr/bin/env python3
"""
Designer bridge ticker: polls the designer API for open requests and dispatches them.

Per SPEC §9:
- Runs after check-build-ready in run-all-tickers.sh
- Uses /Users/gremus/.local/share/ticker-python/python/bin/python3
- Reads owner-admin-token.txt
- Polls /designer/api/admin/<TOKEN>/requests?status=open
- For build requests: macOS notification + append to /tmp/cw-ticker-alerts.txt + mark notified
- For update/bug: write to /tmp/cw-designer-requests.json for run_ticker
- Extract requests are left alone: designer-extract-check.sh (Haiku, every 2 min) handles them

No idle writes: keeps a seen-ids state file to avoid writing on every tick when there are no new requests.
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error
import subprocess
from pathlib import Path

# Paths
HOME = os.environ.get('HOME', '/Users/gremus')
TOKEN_FILE = f"{HOME}/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars/Maps/Library at Celaeno/Server Deployment/owner-admin-token.txt"
STATE_FILE = "/tmp/cw-designer-bridge-seen.json"
REQUESTS_FILE = "/tmp/cw-designer-requests.json"
ALERTS_FILE = "/tmp/cw-ticker-alerts.txt"
SERVER = "https://cwo.freeddns.org"


def load_token():
    """Load the owner admin token from the deployment file."""
    try:
        with open(TOKEN_FILE, 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        print(f"ERROR: Token file not found: {TOKEN_FILE}", file=sys.stderr)
        sys.exit(1)


def load_state():
    """Load the seen request IDs from the state file."""
    if not os.path.exists(STATE_FILE):
        return set()
    try:
        with open(STATE_FILE, 'r') as f:
            data = json.load(f)
            return set(data.get('seen_ids', []))
    except Exception as e:
        print(f"WARN: Could not load state file: {e}", file=sys.stderr)
        return set()


def save_state(seen_ids):
    """Save the seen request IDs to the state file."""
    try:
        with open(STATE_FILE, 'w') as f:
            json.dump({'seen_ids': list(seen_ids)}, f)
    except Exception as e:
        print(f"WARN: Could not save state file: {e}", file=sys.stderr)


def fetch_open_requests(token):
    """Fetch open designer requests from the server."""
    url = f"{SERVER}/designer/api/admin/{token}/requests?status=open"
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            data = json.load(response)
            return data.get('requests', [])
    except urllib.error.HTTPError as e:
        print(f"ERROR: HTTP {e.code} fetching requests: {e.reason}", file=sys.stderr)
        return []
    except Exception as e:
        print(f"ERROR: Failed to fetch requests: {e}", file=sys.stderr)
        return []


def mark_notified(token, request_id):
    """Mark a request as notified via POST to the admin API."""
    url = f"{SERVER}/designer/api/admin/{token}/requests/{request_id}"
    data = json.dumps({'status': 'notified'}).encode('utf-8')
    try:
        req = urllib.request.Request(url, data=data, method='POST')
        req.add_header('Content-Type', 'application/json')
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.status == 200
    except Exception as e:
        print(f"WARN: Failed to mark request {request_id} as notified: {e}", file=sys.stderr)
        return False


def send_notification(title, message):
    """Send a macOS notification with sound Glass."""
    try:
        subprocess.run([
            'osascript', '-e',
            f'display notification "{message}" with title "{title}" sound name "Glass"'
        ], check=False, timeout=5)
    except Exception as e:
        print(f"WARN: Failed to send notification: {e}", file=sys.stderr)


def append_to_alerts(text):
    """Append a line to the ticker alerts file."""
    try:
        with open(ALERTS_FILE, 'a') as f:
            f.write(text + '\n')
    except Exception as e:
        print(f"WARN: Failed to append to alerts file: {e}", file=sys.stderr)


def write_requests_file(requests):
    """Write the designer requests file for the ticker to pick up."""
    try:
        with open(REQUESTS_FILE, 'w') as f:
            json.dump(requests, f, indent=2)
    except Exception as e:
        print(f"ERROR: Failed to write requests file: {e}", file=sys.stderr)


def main():
    token = load_token()
    seen_ids = load_state()

    # Fetch open requests
    requests = fetch_open_requests(token)

    if not requests:
        # No open requests — don't touch any files, no idle writes
        return

    # Build requests: notify once, then they move to "notified"
    for req in requests:
        if req['type'] != 'build' or req['id'] in seen_ids:
            continue
        faction = req.get('faction', 'Unknown')
        user = req.get('user', 'unknown')
        title = "Faction design ready"
        message = f"Prompt Claude to execute the build for {faction} ({user})"
        send_notification(title, message)

        alert_line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {title}: {message}"
        append_to_alerts(alert_line)

        mark_notified(token, req['id'])
        seen_ids.add(req['id'])
        save_state(seen_ids)
        print(f"[build] {faction} — notified owner")

    # Ticker requests stay queued until the ticker marks them done, so a
    # crashed tick is retried. Only rewrite the file when the list changes.
    ticker_reqs = [r for r in requests if r['type'] in ('update', 'bug')]
    if not ticker_reqs:
        # Clear a stale file (e.g. one that only held extract requests) so the
        # 15-min ticker doesn't start a Sonnet tick for nothing.
        if os.path.exists(REQUESTS_FILE):
            os.remove(REQUESTS_FILE)
        return
    try:
        with open(REQUESTS_FILE) as f:
            current = json.load(f)
    except (OSError, ValueError):
        current = None
    if current != ticker_reqs:
        write_requests_file(ticker_reqs)
        for r in ticker_reqs:
            print(f"[{r['type']}] {r.get('faction', 'Unknown')} — queued for ticker")


if __name__ == '__main__':
    main()
