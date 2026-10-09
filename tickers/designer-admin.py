#!/usr/bin/env python3
"""
Designer admin helper for the extraction checker (Haiku every 2 min, Sonnet fallback).

Reads the owner admin token from its file so it never has to appear in a prompt.

  designer-admin.py list-extract            open extract requests (JSON array; [] if none)
  designer-admin.py faction <fid>           full faction record (JSON)
  designer-admin.py image <imageId>         download image, convert to PNG, print local path
  designer-admin.py patch <fid> <ops.json>  POST {"ops": [...]} from the file to admin patch
  designer-admin.py done <rid>              mark request done
  designer-admin.py handoff <rid> <reason>  queue request for the Sonnet fallback

Requests that the Sonnet fallback has already failed MAX_ATTEMPTS times are left out of
list-extract (and the owner is alerted once) so a stuck request cannot loop forever.
"""

import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

HOME = os.environ.get('HOME', '/Users/gremus')
TOKEN_FILE = f"{HOME}/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars/Maps/Library at Celaeno/Server Deployment/owner-admin-token.txt"
SERVER = "https://cwo.freeddns.org"
HANDOFF_FILE = "/tmp/cw-designer-extract-handoff.json"
ATTEMPTS_FILE = "/tmp/cw-designer-extract-attempts.json"
ALERTS_FILE = "/tmp/cw-ticker-alerts.txt"
IMG_DIR = "/tmp/cw-designer-img"
MAX_ATTEMPTS = 3


def token():
    with open(TOKEN_FILE) as f:
        return f.read().strip()


def api(path, body=None):
    url = f"{SERVER}/designer/api/admin/{token()}/{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method='POST' if data else 'GET')
    req.add_header('Content-Type', 'application/json')
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        # Never echo the URL: it contains the token.
        sys.exit(f"ERROR: HTTP {e.code} on admin/{path.split('?')[0]}: {e.read().decode(errors='replace')[:300]}")


def load(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def save(path, value):
    with open(path, 'w') as f:
        json.dump(value, f, indent=2)


def list_extract():
    reqs = [r for r in api('requests?status=open').get('requests', []) if r.get('type') == 'extract']
    attempts = load(ATTEMPTS_FILE, {})
    keep = []
    for r in reqs:
        a = attempts.get(r['id'], {})
        if a.get('count', 0) >= MAX_ATTEMPTS:
            if not a.get('alerted'):
                with open(ALERTS_FILE, 'a') as f:
                    f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Designer extract gave up after "
                            f"{MAX_ATTEMPTS} tries: {r.get('faction', '?')} ({r['id']}) - needs a look\n")
                a['alerted'] = True
                attempts[r['id']] = a
                save(ATTEMPTS_FILE, attempts)
            continue
        keep.append(r)
    print(json.dumps(keep, indent=2))


def image(image_id):
    if not re.fullmatch(r'[A-Za-z0-9_.-]+', image_id):
        sys.exit("ERROR: bad image id")
    os.makedirs(IMG_DIR, exist_ok=True)
    src = os.path.join(IMG_DIR, image_id)
    if not os.path.exists(src):
        urllib.request.urlretrieve(f"{SERVER}/designer/img/{image_id}", src)
    png = os.path.splitext(src)[0] + '.png'
    if not os.path.exists(png):
        subprocess.run(['/usr/bin/sips', '-s', 'format', 'png', src, '--out', png],
                       check=True, capture_output=True)
    print(png)


def handoff(rid, reason):
    queued = load(HANDOFF_FILE, [])
    if not any(h['id'] == rid for h in queued):
        queued.append({'id': rid, 'reason': reason})
    save(HANDOFF_FILE, queued)
    print(f"handed off {rid}")


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd == 'list-extract':
        list_extract()
    elif cmd == 'faction' and len(args) == 1:
        print(json.dumps(api(f'factions/{args[0]}'), indent=2))
    elif cmd == 'image' and len(args) == 1:
        image(args[0])
    elif cmd == 'patch' and len(args) == 2:
        ops = load(args[1], None)
        if ops is None:
            sys.exit(f"ERROR: could not read JSON from {args[1]}")
        if isinstance(ops, dict):
            ops = ops.get('ops', [])
        print(json.dumps(api(f'factions/{args[0]}/patch', {'ops': ops})))
    elif cmd == 'done' and len(args) == 1:
        print(json.dumps(api(f'requests/{args[0]}', {'status': 'done'})))
    elif cmd == 'handoff' and len(args) >= 2:
        handoff(args[0], ' '.join(args[1:]))
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main()
