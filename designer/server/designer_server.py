#!/usr/bin/env python3
"""
CW Faction Designer Backend Server
Python 3 stdlib only. Runs on 127.0.0.1:8091 behind Caddy.
"""
import argparse
import hashlib
import hmac
import json
import os
import re
import secrets
import sys
import threading
import time
from collections import defaultdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlparse

# Global write lock
WRITE_LOCK = threading.Lock()
# Separate lock for terminal-log.json (written while WRITE_LOCK may be held)
TERMINAL_LOCK = threading.Lock()

# Rate limiting storage (IP → timestamps)
REGISTRATION_TIMES: Dict[str, List[float]] = defaultdict(list)
LOGIN_FAILURES: Dict[str, List[float]] = defaultdict(list)

# Built-in reserved acronyms (fallback if reference.json is missing)
DEFAULT_RESERVED_ACRONYMS = [
    "GC", "CC", "BG", "YS", "SL", "WW", "OW", "AN", "TS", "DS",
    "FB", "TT", "BB", "CS", "DC", "TI", "FBE", "XSS"
]


def load_json(path: Path) -> Dict:
    """Load JSON from file, return empty dict if not found."""
    if not path.exists():
        return {}
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def atomic_write(path: Path, data: Dict):
    """Atomic write with fsync."""
    tmp = path.parent / f"{path.name}.tmp"
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def get_client_ip(handler, headers: Dict[str, str]) -> str:
    """Extract client IP, trusting X-Forwarded-For only from 127.0.0.1."""
    client = handler.client_address[0]
    if client == "127.0.0.1" and "X-Forwarded-For" in headers:
        return headers["X-Forwarded-For"].split(",")[0].strip()
    return client


def number_terminal_entries(log: Dict) -> bool:
    """Give every terminal-log row a fixed sequence number "n": oldest is 1, new rows count up.
    nextN is kept so numbers are never reused after old rows are trimmed. Returns True if anything changed."""
    entries = log.setdefault("entries", [])
    missing = [e for e in entries if not isinstance(e.get("n"), int)]
    if not missing:
        return False
    nxt = max([log.get("nextN", 1)] + [e["n"] + 1 for e in entries if isinstance(e.get("n"), int)])
    for e in sorted(missing, key=lambda e: e.get("at", 0)):
        e["n"] = nxt
        nxt += 1
    log["nextN"] = nxt
    return True


class FactionDesignerHandler(BaseHTTPRequestHandler):
    server_version = "CWODesigner/1.0"

    def log_message(self, format, *args):
        """Log to stderr."""
        sys.stderr.write(f"{self.address_string()} - [{self.log_date_time_string()}] {format % args}\n")

    def send_json(self, data: Any, code: int = 200):
        """Send JSON response."""
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def send_error_json(self, message: str, code: int = 400):
        """Send error response."""
        self.send_json({"error": message}, code)

    def read_json_body(self) -> Optional[Dict]:
        """Read and parse JSON body."""
        try:
            length = int(self.headers.get('Content-Length', 0))
            if length == 0:
                return {}  # Empty body → empty dict
            if length > 5_000_000:  # 5 MB limit for JSON
                self.send_error_json("Request too large", 413)
                return None
            body = self.rfile.read(length)
            return json.loads(body.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self.send_error_json("Invalid JSON", 400)
            return None

    def read_raw_body(self) -> Optional[bytes]:
        """Read raw body for image uploads."""
        try:
            length = int(self.headers.get('Content-Length', 0))
            if length > 5_000_000:  # 5 MB limit
                self.send_error_json("Image too large (max 5 MB)", 413)
                return None
            return self.rfile.read(length)
        except Exception:
            self.send_error_json("Failed to read body", 400)
            return None

    def get_auth_token(self, body: Optional[Dict] = None) -> Optional[str]:
        """Extract bearer token from Authorization header or body (sendBeacon)."""
        auth = self.headers.get('Authorization', '')
        if auth.startswith('Bearer '):
            return auth[7:]
        if body and 'token' in body:
            return body['token']
        return None

    def verify_session(self, body: Optional[Dict] = None) -> Optional[str]:
        """Verify session token and return username (lowercase), or None."""
        token = self.get_auth_token(body)
        if not token:
            return None

        sessions_file = self.server.data_dir / "sessions.json"
        sessions_data = load_json(sessions_file)
        sessions = sessions_data.get("sessions", {})

        # Prune expired sessions
        now = time.time()
        active = {k: v for k, v in sessions.items() if v.get("expires", 0) > now}
        if len(active) != len(sessions):
            with WRITE_LOCK:
                sessions_data["sessions"] = active
                atomic_write(sessions_file, sessions_data)

        session = active.get(token)
        if session:
            return session.get("user")
        return None

    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()

    def do_GET(self):
        """Handle GET requests."""
        parsed = urlparse(self.path)
        path = parsed.path

        # Health check
        if path == '/designer/api/health':
            self.send_json({"ok": True})
            return

        # User endpoints
        if path == '/designer/api/factions':
            self.handle_list_factions()
            return

        if path.startswith('/designer/api/factions/'):
            parts = path.split('/')
            if len(parts) >= 5:
                fid = parts[4]
                if len(parts) == 5:
                    self.handle_get_faction(fid)
                    return
                elif len(parts) == 6 and parts[5] == 'requests':
                    self.handle_get_faction_requests(fid)
                    return
                elif len(parts) == 6 and parts[5] == 'extract-queue':
                    self.handle_get_extract_queue(fid)
                    return

        # Admin endpoints
        m = re.fullmatch(r'/designer/api/live/([A-Za-z0-9]{2,3})/values', path)
        if m:
            self.handle_live_values(m.group(1))
            return

        if path.startswith('/designer/api/admin/'):
            self.handle_admin_get(path)
            return

        self.send_error_json("Not found", 404)

    def do_POST(self):
        """Handle POST requests."""
        parsed = urlparse(self.path)
        path = parsed.path

        # Public endpoints
        if path == '/designer/api/register':
            self.handle_register()
            return
        if path == '/designer/api/login':
            self.handle_login()
            return
        if path == '/designer/api/logout':
            self.handle_logout()
            return

        # Image upload
        if path == '/designer/api/images':
            self.handle_upload_image()
            return

        # Faction endpoints
        if path == '/designer/api/factions':
            self.handle_create_faction()
            return

        if path.startswith('/designer/api/factions/'):
            parts = path.split('/')
            if len(parts) >= 5:
                fid = parts[4]
                if len(parts) == 6:
                    action = parts[5]
                    if action == 'patch':
                        self.handle_patch_faction(fid)
                        return
                    elif action == 'close-session':
                        self.handle_close_session(fid)
                        return
                    elif action == 'rollback':
                        self.handle_rollback(fid)
                        return
                    elif action == 'delete-version':
                        self.handle_delete_version(fid)
                        return
                    elif action == 'request':
                        self.handle_create_request(fid)
                        return

        # Admin endpoints
        if path.startswith('/designer/api/admin/'):
            self.handle_admin_post(path)
            return

        self.send_error_json("Not found", 404)

    # ── User Authentication ──────────────────────────────────────────────────────

    def handle_register(self):
        """POST /designer/api/register"""
        body = self.read_json_body()
        if not body:
            return

        username = body.get('username', '').strip()
        password = body.get('password', '')

        # Validate username
        if not re.match(r'^[A-Za-z0-9_.-]{3,24}$', username):
            self.send_error_json("Username must be 3-24 characters: letters, numbers, _, ., -")
            return

        # Validate password
        if len(password) < 4:
            self.send_error_json("Password must be at least 4 characters")
            return

        # Rate limit: 5 registrations per IP per day (100 for localhost/testing)
        client_ip = get_client_ip(self, dict(self.headers))
        now = time.time()
        cutoff = now - 86400  # 24 hours
        REGISTRATION_TIMES[client_ip] = [t for t in REGISTRATION_TIMES[client_ip] if t > cutoff]
        limit = 100 if client_ip in ('127.0.0.1', '::1', 'localhost') else 5
        if len(REGISTRATION_TIMES[client_ip]) >= limit:
            self.send_error_json("Registration limit exceeded. Try again later.", 429)
            return
        REGISTRATION_TIMES[client_ip].append(now)

        # Load users
        users_file = self.server.data_dir / "users.json"
        users_data = load_json(users_file) or {"users": {}}
        users = users_data.get("users", {})

        username_lc = username.lower()
        if username_lc in users:
            self.send_error_json("Username already exists")
            return

        # Hash password
        salt = secrets.token_bytes(16)
        pw_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 200_000)

        # Create user
        with WRITE_LOCK:
            users[username_lc] = {
                "username": username,  # preserve case
                "salt": salt.hex(),
                "hash": pw_hash.hex(),
                "iter": 200_000,
                "created": int(now),
                "lastLogin": int(now),
                "imageBytes": 0
            }
            users_data["users"] = users
            atomic_write(users_file, users_data)

        # Create session
        token = secrets.token_urlsafe(32)
        sessions_file = self.server.data_dir / "sessions.json"
        sessions_data = load_json(sessions_file) or {"sessions": {}}

        with WRITE_LOCK:
            sessions_data["sessions"][token] = {
                "user": username_lc,
                "expires": int(now + 2_592_000)  # 30 days
            }
            atomic_write(sessions_file, sessions_data)

        self.send_json({"token": token, "username": username})

    def handle_login(self):
        """POST /designer/api/login"""
        body = self.read_json_body()
        if not body:
            return

        username = body.get('username', '').strip().lower()
        password = body.get('password', '')

        # Throttle: 10 failures per username per 15 min
        now = time.time()
        cutoff = now - 900  # 15 minutes
        LOGIN_FAILURES[username] = [t for t in LOGIN_FAILURES[username] if t > cutoff]
        if len(LOGIN_FAILURES[username]) >= 10:
            self.send_error_json("Too many failed login attempts. Try again later.", 429)
            return

        # Load users
        users_file = self.server.data_dir / "users.json"
        users_data = load_json(users_file) or {"users": {}}
        users = users_data.get("users", {})

        user = users.get(username)
        if not user:
            LOGIN_FAILURES[username].append(now)
            self.send_error_json("Invalid username or password", 401)
            return

        # Verify password (constant-time)
        salt = bytes.fromhex(user['salt'])
        expected = bytes.fromhex(user['hash'])
        actual = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, user.get('iter', 200_000))

        if not hmac.compare_digest(expected, actual):
            LOGIN_FAILURES[username].append(now)
            self.send_error_json("Invalid username or password", 401)
            return

        # Update last login
        with WRITE_LOCK:
            user['lastLogin'] = int(now)
            atomic_write(users_file, users_data)

        # Create session
        token = secrets.token_urlsafe(32)
        sessions_file = self.server.data_dir / "sessions.json"
        sessions_data = load_json(sessions_file) or {"sessions": {}}

        with WRITE_LOCK:
            sessions_data["sessions"][token] = {
                "user": username,
                "expires": int(now + 2_592_000)  # 30 days
            }
            atomic_write(sessions_file, sessions_data)

        self.send_json({"token": token, "username": user['username']})

    def handle_logout(self):
        """POST /designer/api/logout"""
        body = self.read_json_body()
        token = self.get_auth_token(body)

        if token:
            sessions_file = self.server.data_dir / "sessions.json"
            sessions_data = load_json(sessions_file)
            if token in sessions_data.get("sessions", {}):
                with WRITE_LOCK:
                    del sessions_data["sessions"][token]
                    atomic_write(sessions_file, sessions_data)

        self.send_json({})

    # ── Faction Management ───────────────────────────────────────────────────────

    def handle_list_factions(self):
        """GET /designer/api/factions"""
        username = self.verify_session()
        if not username:
            self.send_error_json("Unauthorized", 401)
            return

        factions_dir = self.server.data_dir / "factions"
        factions = []

        if factions_dir.exists():
            for fid_dir in factions_dir.iterdir():
                if not fid_dir.is_dir():
                    continue
                faction_file = fid_dir / "faction.json"
                if not faction_file.exists():
                    continue
                faction = load_json(faction_file)
                if faction.get("owner") == username:
                    factions.append({
                        "id": faction["id"],
                        "name": faction["name"],
                        "acronym": faction["acronym"],
                        "current": faction["current"],
                        "buildStatus": faction.get("build", {}).get("status", "none"),
                        "updated": faction["updated"]
                    })
                elif username in faction.get("viewers", []):
                    # Shared with this user as read only (set by the admin)
                    factions.append({
                        "id": faction["id"],
                        "name": faction["name"],
                        "acronym": faction["acronym"],
                        "current": faction["current"],
                        "buildStatus": faction.get("build", {}).get("status", "none"),
                        "updated": faction["updated"],
                        "readOnly": True,
                        "owner": faction["owner"],
                        "ownerName": self.display_name(faction["owner"])
                    })

        factions.sort(key=lambda f: f["updated"], reverse=True)
        self.send_json({"factions": factions})

    def handle_create_faction(self):
        """POST /designer/api/factions"""
        username = self.verify_session()
        if not username:
            self.send_error_json("Unauthorized", 401)
            return

        body = self.read_json_body()
        if not body:
            return

        name = body.get('name', '').strip()
        acronym = body.get('acronym', '').strip().upper()

        # Validate name
        if len(name) < 5:
            self.send_error_json("Faction name must be at least 5 characters")
            return

        # Validate acronym
        if not re.match(r'^[A-Z0-9]{2,3}$', acronym):
            self.send_error_json("Acronym must be 2-3 letters or digits")
            return

        # Check reserved
        reserved = self.server.reserved_acronyms
        if acronym in reserved:
            self.send_error_json(f"Acronym {acronym} is reserved")
            return

        # Check for duplicate acronym
        factions_dir = self.server.data_dir / "factions"
        factions_dir.mkdir(parents=True, exist_ok=True)

        for fid_dir in factions_dir.iterdir():
            if not fid_dir.is_dir():
                continue
            faction_file = fid_dir / "faction.json"
            if faction_file.exists():
                existing = load_json(faction_file)
                if existing.get("acronym") == acronym:
                    self.send_error_json(f"Acronym {acronym} is already in use")
                    return

        # Check user's faction count
        user_factions = sum(1 for fd in factions_dir.iterdir()
                          if fd.is_dir() and (fd / "faction.json").exists()
                          and load_json(fd / "faction.json").get("owner") == username)

        if user_factions >= 20:
            self.send_error_json("Maximum 20 factions per user")
            return

        # Create faction
        fid = secrets.token_urlsafe(9).replace('_', '').replace('-', '').lower()[:12]
        now = int(time.time())

        faction = {
            "id": fid,
            "owner": username,
            "name": name,
            "acronym": acronym,
            "created": now,
            "updated": now,
            "current": 1,
            "maxVersion": 1,
            "versions": [{"n": 1, "from": None, "sections": [], "created": now, "deleted": False}],
            "session": {"n": 1, "sections": [], "last": now},
            "build": {"status": "none", "liveVersion": None, "requestedAt": None, "builtAt": None, "history": []},
            "liveGameVersions": [],
            "design": self.new_design()
        }

        with WRITE_LOCK:
            faction_dir = factions_dir / fid
            faction_dir.mkdir(exist_ok=True)
            (faction_dir / "v").mkdir(exist_ok=True)

            faction_file = faction_dir / "faction.json"
            atomic_write(faction_file, faction)

            # Write initial version snapshot
            v_file = faction_dir / "v" / "1.json"
            atomic_write(v_file, faction["design"])

        self.send_json(faction)

    def handle_get_faction(self, fid: str):
        """GET /designer/api/factions/<fid>"""
        username = self.verify_session()
        if not username:
            self.send_error_json("Unauthorized", 401)
            return

        faction = self.load_faction(fid)
        if not faction:
            self.send_error_json("Faction not found", 404)
            return

        read_only = faction["owner"] != username
        if read_only and username not in faction.get("viewers", []):
            self.send_error_json("Forbidden", 403)
            return

        response = dict(faction)
        if read_only:
            response["readOnly"] = True
            response["ownerName"] = self.display_name(faction["owner"])
        response["builtDesign"] = self.built_design_with_overrides(fid, faction)
        response["liveValues"] = self.load_live_values(fid)
        response["extractQueue"] = self.extract_queue_position(fid)
        self.send_json(response)

    def extract_queue_position(self, fid: str) -> Optional[Dict]:
        """Extraction status of this faction's oldest open extract, or None when it has nothing open.
        {state: "waiting"} = the checker has not picked it up yet; {state: "queued", position: N} = picked
        up, N-th of the open extracts not yet started (oldest first); {state: "in_process"} = being worked on.
        The checker's designer-admin.py marks pickedUp (list-extract) and startedAt (faction <fid>)."""
        requests = (load_json(self.server.data_dir / "requests.json") or {}).get("requests", [])
        queue = sorted((r for r in requests if r.get("type") == "extract" and r.get("status") == "open"),
                       key=lambda r: r.get("created", 0))
        mine = next((r for r in queue if r.get("fid") == fid), None)
        if not mine:
            return None
        if mine.get("startedAt"):
            return {"state": "in_process"}
        if not mine.get("pickedUp"):
            return {"state": "waiting"}
        waiting = [r for r in queue if not r.get("startedAt")]
        return {"state": "queued", "position": waiting.index(mine) + 1}

    def handle_get_extract_queue(self, fid: str):
        """GET /designer/api/factions/<fid>/extract-queue -> {status} (null when nothing open)"""
        username = self.verify_session()
        if not username:
            self.send_error_json("Unauthorized", 401)
            return
        faction = self.load_faction(fid)
        if not faction:
            self.send_error_json("Faction not found", 404)
            return
        if faction["owner"] != username and username not in faction.get("viewers", []):
            self.send_error_json("Forbidden", 403)
            return
        self.send_json({"status": self.extract_queue_position(fid)})

    def handle_patch_faction(self, fid: str):
        """POST /designer/api/factions/<fid>/patch"""
        username = self.verify_session()
        if not username:
            self.send_error_json("Unauthorized", 401)
            return

        body = self.read_json_body()
        if not body:
            return

        ops = body.get('ops', [])
        if not isinstance(ops, list):
            self.send_error_json("ops must be an array")
            return

        with WRITE_LOCK:
            faction = self.load_faction(fid)
            if not faction:
                self.send_error_json("Faction not found", 404)
                return

            if faction["owner"] != username:
                self.send_error_json("Forbidden", 403)
                return

            # Apply ops
            for op in ops:
                if not self.apply_patch_op(faction, op, fid):
                    return  # Error already sent

            # Save faction
            faction["updated"] = int(time.time())
            faction_file = self.server.data_dir / "factions" / fid / "faction.json"
            atomic_write(faction_file, faction)

            # Always rewrite current version snapshot
            v_file = self.server.data_dir / "factions" / fid / "v" / f"{faction['current']}.json"
            atomic_write(v_file, faction["design"])

        self.send_json({
            "current": faction["current"],
            "maxVersion": faction["maxVersion"],
            "versions": faction["versions"],
            "session": faction["session"],
            "updated": faction["updated"]
        })

    def apply_patch_op(self, faction: Dict, op: Dict, fid: str) -> bool:
        """Apply a single patch operation. Return False on error."""
        op_type = op.get('op')
        path = op.get('path', '')

        # Extract section key (first path segment)
        parts = path.split('.')
        if not parts:
            self.send_error_json("Invalid path")
            return False

        section = parts[0]
        valid_sections = ['ae', 'ufa', 'setup', 'units', 'sbr', 'sb', 'region', 'tokens', 'custom', 'menus', 'card', 'sbImages', 'sbImagesB', 'meta']
        if section not in valid_sections:
            self.send_error_json(f"Unknown section: {section}")
            return False

        # Determine if this is an addition or change
        is_addition = self.is_addition(faction, op)

        # Check if version is locked
        current = faction["current"]
        max_version = faction["maxVersion"]
        live_version = faction.get("build", {}).get("liveVersion")
        is_locked = current < max_version or current == live_version

        # Check open session
        now = time.time()
        session = faction["session"]
        is_open_session = (
            session["n"] == current and
            now - session["last"] < 600 and
            section in session["sections"]
        )

        # Decide: new version or in-place
        if is_locked:
            self.create_new_version(faction, section, fid)
        elif is_addition:
            # Apply in place, add section to version
            pass  # Will apply below
        elif not is_open_session:
            self.create_new_version(faction, section, fid)

        # Apply the operation
        if not self.apply_op_to_design(faction["design"], op):
            return False

        # Update session
        session["last"] = int(now)
        if session["n"] == faction["current"]:
            if section not in session["sections"]:
                session["sections"].append(section)
        else:
            session["n"] = faction["current"]
            session["sections"] = [section]

        # Add section to current version's sections if not present
        for v in faction["versions"]:
            if v["n"] == faction["current"]:
                if section not in v["sections"]:
                    v["sections"].append(section)
                break

        return True

    def is_addition(self, faction: Dict, op: Dict) -> bool:
        """Check if operation is an addition (empty→non-empty)."""
        op_type = op.get('op')
        path = op.get('path', '')
        design = faction["design"]

        if op_type == 'addRow':
            # Check if the row being added is completely empty
            row = op.get('row', {})
            return self.is_blank_row(row)

        if op_type == 'deleteRow':
            # Deleting an empty row is an addition
            table_path = op.get('path', '')
            row_id = op.get('id')
            row = self.find_row(design, table_path, row_id)
            if row:
                return self.is_blank_row(row)
            return True

        if op_type == 'set':
            value = op.get('value')
            # Get current value
            current = self.get_path_value(design, path)

            # Empty values: "", None, []
            current_empty = current in ("", None, [])
            value_empty = value in ("", None, [])

            # Addition if current is empty and new is non-empty
            return current_empty and not value_empty

        if op_type == 'replaceSection':
            section = path.split('.')[0] if '.' in path else path
            current_section = design.get(section, {})
            return self.is_section_empty(section, current_section)

        return False

    def is_blank_row(self, row: Dict) -> bool:
        """Check if a row is completely blank (all defaults)."""
        for k, v in row.items():
            if k == 'id':
                continue
            if v not in ("", None, [], False, 0):
                # Check default values
                if k == 'sign' and v == '+':
                    continue
                if k == 'kind' and v == 'fixed':
                    continue
                if k == 'onMap' and v is True:
                    continue
                if k == 'mapScale' and v == 1.0:
                    continue
                if k == 'hasNum' and v is False:
                    continue
                if k == 'hasCost' and v is False:
                    continue
                if k == 'hasEffect' and v is False:
                    continue
                if k == 'hasSubtitle' and v is False:
                    continue
                if k == 'cancel' and v is False:
                    continue
                if k == 'skip' and v is False:
                    continue
                if k in ('done', 'multiSelect') and v is False:
                    continue
                if k == 'leadsToNext' and v is False:
                    continue
                return False
        return True

    def is_section_empty(self, section: str, data: Any) -> bool:
        """Check if a section matches defaults."""
        defaults = self.new_design()
        return data == defaults.get(section)

    def create_new_version(self, faction: Dict, section: str, fid: str):
        """Create a new version and freeze the current one."""
        current = faction["current"]
        max_version = faction["maxVersion"]

        # Freeze current version (if not already frozen)
        v_file = self.server.data_dir / "factions" / fid / "v" / f"{current}.json"
        if not v_file.exists():
            atomic_write(v_file, faction["design"])

        # Create new version
        new_n = max_version + 1
        now = int(time.time())

        faction["versions"].append({
            "n": new_n,
            "from": current,
            "sections": [section],
            "created": now,
            "deleted": False
        })

        faction["current"] = new_n
        faction["maxVersion"] = new_n
        faction["session"] = {"n": new_n, "sections": [section], "last": now}

    def apply_op_to_design(self, design: Dict, op: Dict) -> bool:
        """Apply operation to design object."""
        op_type = op.get('op')
        path = op.get('path', '')

        if op_type == 'set':
            value = op.get('value')
            # Size limit
            if isinstance(value, str) and len(value) > 20_000:
                self.send_error_json("Value too large (max 20,000 characters)")
                return False
            self.set_path_value(design, path, value)
            return True

        elif op_type == 'addRow':
            table_path = path
            row = op.get('row')
            if not row or 'id' not in row:
                self.send_error_json("Row must have an id")
                return False
            table = self.get_path_value(design, table_path)
            if not isinstance(table, list):
                self.send_error_json(f"Path {table_path} is not an array")
                return False
            table.append(row)
            return True

        elif op_type == 'deleteRow':
            table_path = path
            row_id = op.get('id')
            table = self.get_path_value(design, table_path)
            if not isinstance(table, list):
                self.send_error_json(f"Path {table_path} is not an array")
                return False
            table[:] = [r for r in table if r.get('id') != row_id]
            return True

        elif op_type == 'replaceSection':
            section = path.split('.')[0] if '.' in path else path
            value = op.get('value')
            design[section] = value
            return True

        else:
            self.send_error_json(f"Unknown operation: {op_type}")
            return False

    def get_path_value(self, obj: Any, path: str) -> Any:
        """Get value at dot path."""
        parts = path.split('.')
        current = obj
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            elif isinstance(current, list):
                # Array index or row id
                if part.isdigit():
                    idx = int(part)
                    if 0 <= idx < len(current):
                        current = current[idx]
                    else:
                        return None
                else:
                    # Find by row id
                    current = next((r for r in current if r.get('id') == part), None)
            else:
                return None
        return current

    def set_path_value(self, obj: Any, path: str, value: Any):
        """Set value at dot path."""
        parts = path.split('.')
        current = obj
        for i, part in enumerate(parts[:-1]):
            if isinstance(current, dict):
                if part not in current:
                    current[part] = {}
                current = current[part]
            elif isinstance(current, list):
                if part.isdigit():
                    current = current[int(part)]
                else:
                    current = next((r for r in current if r.get('id') == part), None)

        last = parts[-1]
        if current is None:
            return
        if isinstance(current, dict):
            current[last] = value
        elif isinstance(current, list):
            if last.isdigit():
                current[int(last)] = value
            else:
                row = next((r for r in current if r.get('id') == last), None)
                if row:
                    row[last] = value

    def find_row(self, design: Dict, table_path: str, row_id: str) -> Optional[Dict]:
        """Find a row by id in a table."""
        table = self.get_path_value(design, table_path)
        if isinstance(table, list):
            return next((r for r in table if r.get('id') == row_id), None)
        return None

    def handle_close_session(self, fid: str):
        """POST /designer/api/factions/<fid>/close-session"""
        username = self.verify_session()
        if not username:
            self.send_error_json("Unauthorized", 401)
            return

        with WRITE_LOCK:
            faction = self.load_faction(fid)
            if not faction:
                self.send_error_json("Faction not found", 404)
                return

            if faction["owner"] != username:
                self.send_error_json("Forbidden", 403)
                return

            # Clear session by resetting last time to far past
            faction["session"]["last"] = 0

            faction_file = self.server.data_dir / "factions" / fid / "faction.json"
            atomic_write(faction_file, faction)

        self.send_json({})

    def handle_rollback(self, fid: str):
        """POST /designer/api/factions/<fid>/rollback"""
        username = self.verify_session()
        if not username:
            self.send_error_json("Unauthorized", 401)
            return

        body = self.read_json_body()
        if not body:
            return

        version = body.get('version')
        if not isinstance(version, int) or version < 1:
            self.send_error_json("Invalid version")
            return

        with WRITE_LOCK:
            faction = self.load_faction(fid)
            if not faction:
                self.send_error_json("Faction not found", 404)
                return

            if faction["owner"] != username:
                self.send_error_json("Forbidden", 403)
                return

            # Check version exists and not deleted
            version_info = next((v for v in faction["versions"] if v["n"] == version), None)
            if not version_info or version_info.get("deleted"):
                self.send_error_json("Version not found or deleted", 404)
                return

            # Save current snapshot
            current = faction["current"]
            v_file = self.server.data_dir / "factions" / fid / "v" / f"{current}.json"
            if not v_file.exists():
                atomic_write(v_file, faction["design"])

            # Load target version
            target_file = self.server.data_dir / "factions" / fid / "v" / f"{version}.json"
            if not target_file.exists():
                self.send_error_json("Version snapshot not found", 404)
                return

            design = load_json(target_file)
            faction["design"] = design
            faction["current"] = version
            faction["session"] = {"n": version, "sections": [], "last": 0}
            faction["updated"] = int(time.time())

            faction_file = self.server.data_dir / "factions" / fid / "faction.json"
            atomic_write(faction_file, faction)

        self.send_json(faction)

    def handle_delete_version(self, fid: str):
        """POST /designer/api/factions/<fid>/delete-version"""
        username = self.verify_session()
        if not username:
            self.send_error_json("Unauthorized", 401)
            return

        body = self.read_json_body()
        if not body:
            return

        version = body.get('version')
        if not isinstance(version, int) or version < 1:
            self.send_error_json("Invalid version")
            return

        with WRITE_LOCK:
            faction = self.load_faction(fid)
            if not faction:
                self.send_error_json("Faction not found", 404)
                return

            if faction["owner"] != username:
                self.send_error_json("Forbidden", 403)
                return

            # Check constraints
            if version == faction["current"]:
                self.send_error_json("Cannot delete current version")
                return

            live_version = faction.get("build", {}).get("liveVersion")
            if version == live_version:
                self.send_error_json("Cannot delete live version")
                return

            if version in faction.get("liveGameVersions", []):
                self.send_error_json("Cannot delete version used in live game")
                return

            # Check it's not the only non-deleted version
            non_deleted = [v for v in faction["versions"] if not v.get("deleted")]
            if len(non_deleted) <= 1:
                self.send_error_json("Cannot delete the only version")
                return

            # Mark deleted
            for v in faction["versions"]:
                if v["n"] == version:
                    v["deleted"] = True
                    v["sections"] = ["DELETED"]
                    break

            # Remove snapshot file
            v_file = self.server.data_dir / "factions" / fid / "v" / f"{version}.json"
            if v_file.exists():
                v_file.unlink()

            faction["updated"] = int(time.time())
            faction_file = self.server.data_dir / "factions" / fid / "faction.json"
            atomic_write(faction_file, faction)

        self.send_json(faction)

    # ── Image Upload ─────────────────────────────────────────────────────────────

    def handle_upload_image(self, admin: bool = False):
        """POST /designer/api/images (or admin/<TOKEN>/images: extractor uploads, no user quota)"""
        username = None
        if not admin:
            username = self.verify_session()
            if not username:
                self.send_error_json("Unauthorized", 401)
                return

        content_type = self.headers.get('Content-Type', '')
        ext = None
        magic_required = None

        if content_type == 'image/webp':
            ext = 'webp'
            magic_required = b'RIFF'  # RIFF...WEBP
        elif content_type == 'image/png':
            ext = 'png'
            magic_required = b'\x89PNG'
        elif content_type == 'image/jpeg':
            ext = 'jpg'
            magic_required = b'\xff\xd8\xff'
        else:
            self.send_error_json("Content-Type must be image/webp, image/png, or image/jpeg")
            return

        body = self.read_raw_body()
        if not body:
            return

        # Check magic bytes
        if not body.startswith(magic_required):
            self.send_error_json(f"Invalid {ext} file (magic bytes mismatch)")
            return

        # Hash for deduplication
        sha = hashlib.sha256(body).hexdigest()
        image_id = f"{sha}.{ext}"

        images_dir = self.server.data_dir / "images"
        images_dir.mkdir(parents=True, exist_ok=True)
        image_file = images_dir / image_id

        # Check quota (300 MB per user; admin uploads have no user)
        users_file = self.server.data_dir / "users.json"
        users_data = load_json(users_file)
        users = users_data.get("users", {})
        user = users.get(username, {})

        if not image_file.exists() and admin:
            with WRITE_LOCK:
                with open(image_file, 'wb') as f:
                    f.write(body)
                    f.flush()
                    os.fsync(f.fileno())
        elif not image_file.exists():
            # New image, check quota
            current_bytes = user.get("imageBytes", 0)
            if current_bytes + len(body) > 300_000_000:
                self.send_error_json("Image quota exceeded (300 MB per user)")
                return

            with WRITE_LOCK:
                # Write image
                with open(image_file, 'wb') as f:
                    f.write(body)
                    f.flush()
                    os.fsync(f.fileno())

                # Update quota
                user["imageBytes"] = current_bytes + len(body)
                atomic_write(users_file, users_data)

        url = f"/designer/img/{image_id}"
        self.send_json({"id": image_id, "url": url})

    # ── Requests ─────────────────────────────────────────────────────────────────

    def handle_create_request(self, fid: str):
        """POST /designer/api/factions/<fid>/request"""
        username = self.verify_session()
        if not username:
            self.send_error_json("Unauthorized", 401)
            return

        body = self.read_json_body()
        if not body:
            return

        req_type = body.get('type')
        text = body.get('text', '')
        data = body.get('data', {})

        valid_types = ['build', 'update', 'simple_update', 'extract', 'bug']
        if req_type not in valid_types:
            self.send_error_json(f"Invalid request type. Must be one of: {', '.join(valid_types)}")
            return

        faction = self.load_faction(fid)
        if not faction:
            self.send_error_json("Faction not found", 404)
            return

        if faction["owner"] != username:
            self.send_error_json("Forbidden", 403)
            return

        if req_type == 'simple_update':
            self.handle_simple_update_push(fid, faction, username, data)
            return

        # Load requests
        requests_file = self.server.data_dir / "requests.json"
        requests_data = load_json(requests_file) or {"requests": []}
        requests = requests_data.get("requests", [])

        # Check for duplicate (same type + fid + data)
        for existing in requests:
            if (existing.get("type") == req_type and
                existing.get("fid") == fid and
                existing.get("status") == "open" and
                existing.get("data") == data):
                # Return existing
                self.send_json(existing)
                return

        # Create new request
        now = int(time.time())
        req_id = f"r_{secrets.token_urlsafe(6)}"

        request = {
            "id": req_id,
            "type": req_type,
            "fid": fid,
            "faction": faction["name"],
            "acronym": faction["acronym"],
            "user": username,
            "status": "open",
            "created": now,
            "updated": now,
            "text": text,
            "data": data
        }

        with WRITE_LOCK:
            requests.append(request)
            requests_data["requests"] = requests
            atomic_write(requests_file, requests_data)
            # Every designer prompt also goes into the admin console's Claude terminal log
            self.add_terminal_entry(self.terminal_type(request), self.display_name(username),
                                    text or f"{req_type} request for {faction['name']}",
                                    "Waiting to be picked up.", ref=req_id)

        self.send_json(request)

    def handle_get_faction_requests(self, fid: str):
        """GET /designer/api/factions/<fid>/requests"""
        username = self.verify_session()
        if not username:
            self.send_error_json("Unauthorized", 401)
            return

        faction = self.load_faction(fid)
        if not faction:
            self.send_error_json("Faction not found", 404)
            return

        if faction["owner"] != username:
            self.send_error_json("Forbidden", 403)
            return

        requests_file = self.server.data_dir / "requests.json"
        requests_data = load_json(requests_file) or {"requests": []}
        requests = requests_data.get("requests", [])

        faction_requests = [r for r in requests if r.get("fid") == fid]
        faction_requests.sort(key=lambda r: r.get("created", 0), reverse=True)

        self.send_json({"requests": faction_requests})

    # ── Admin Endpoints ──────────────────────────────────────────────────────────

    def verify_admin_token(self, path: str) -> Optional[str]:
        """Extract and verify admin token from path. Return token if valid."""
        # Path format: /designer/api/admin/<TOKEN>/...
        parts = path.split('/')
        if len(parts) < 5 or parts[3] != 'admin':
            return None

        token = parts[4]
        if not token:
            return None

        # Hash and compare
        token_hash = hashlib.sha256(token.encode('utf-8')).hexdigest()

        if not self.server.admin_token_hash_file.exists():
            return None

        with open(self.server.admin_token_hash_file, 'r') as f:
            expected_hash = f.read().strip()

        if hmac.compare_digest(token_hash, expected_hash):
            return token

        return None

    def handle_admin_get(self, path: str):
        """Handle admin GET requests."""
        if not self.verify_admin_token(path):
            self.send_error_json("Not found", 404)
            return

        # Extract endpoint after token
        parts = path.split('/')
        if len(parts) < 6:
            self.send_error_json("Invalid admin path", 400)
            return

        endpoint = parts[5]

        if endpoint == 'users':
            self.handle_admin_users()
        elif endpoint == 'requests':
            self.handle_admin_requests()
        elif endpoint == 'factions' and len(parts) >= 7:
            fid = parts[6]
            self.handle_admin_get_faction(fid)
        elif endpoint == 'view-faction' and len(parts) >= 7:
            self.handle_admin_view_faction(parts[6])
        elif endpoint == 'image-usage':
            self.handle_admin_image_usage()
        elif endpoint == 'terminal-log':
            with TERMINAL_LOCK:
                path = self.server.data_dir / "terminal-log.json"
                log = load_json(path) or {"entries": []}
                if number_terminal_entries(log):
                    atomic_write(path, log)
            self.send_json({"entries": sorted(log.get("entries", []), key=lambda e: e.get("at", 0), reverse=True)})
        else:
            self.send_error_json("Unknown admin endpoint", 404)

    def handle_admin_post(self, path: str):
        """Handle admin POST requests."""
        if not self.verify_admin_token(path):
            self.send_error_json("Not found", 404)
            return

        parts = path.split('/')
        if len(parts) < 6:
            self.send_error_json("Invalid admin path", 400)
            return

        endpoint = parts[5]

        if endpoint == 'reset-password':
            self.handle_admin_reset_password()
        elif endpoint == 'delete':
            self.handle_admin_delete()
        elif endpoint == 'images':
            self.handle_upload_image(admin=True)
        elif endpoint == 'import-faction':
            self.handle_admin_import_faction()
        elif endpoint == 'terminal-log':
            self.handle_admin_terminal_log(parts[6] if len(parts) >= 7 else None)
        elif endpoint == 'requests' and len(parts) >= 7:
            rid = parts[6]
            self.handle_admin_update_request(rid)
        elif endpoint == 'factions' and len(parts) >= 7:
            fid = parts[6]
            if len(parts) >= 8:
                action = parts[7]
                if action == 'patch':
                    self.handle_admin_patch_faction(fid)
                elif action == 'build-status':
                    self.handle_admin_build_status(fid)
                elif action == 'live-game-versions':
                    self.handle_admin_live_game_versions(fid)
                elif action == 'viewers':
                    self.handle_admin_viewers(fid)
                else:
                    self.send_error_json("Unknown admin endpoint", 404)
            else:
                self.send_error_json("Invalid admin path", 400)
        else:
            self.send_error_json("Unknown admin endpoint", 404)

    def handle_admin_users(self):
        """GET admin/users"""
        users_file = self.server.data_dir / "users.json"
        users_data = load_json(users_file) or {"users": {}}
        users = users_data.get("users", {})

        result = []
        for username, user in users.items():
            # Get user's factions
            factions_dir = self.server.data_dir / "factions"
            user_factions = []

            if factions_dir.exists():
                for fid_dir in factions_dir.iterdir():
                    if not fid_dir.is_dir():
                        continue
                    faction_file = fid_dir / "faction.json"
                    if faction_file.exists():
                        faction = load_json(faction_file)
                        if faction.get("owner") == username:
                            user_factions.append({
                                "id": faction["id"],
                                "name": faction["name"],
                                "acronym": faction["acronym"],
                                "current": faction["current"],
                                "buildStatus": faction.get("build", {}).get("status", "none"),
                                "liveVersion": faction.get("build", {}).get("liveVersion"),
                                "updated": faction["updated"]
                            })

            result.append({
                "username": user["username"],
                "created": user["created"],
                "lastLogin": user.get("lastLogin"),
                "imageBytes": user.get("imageBytes", 0),
                "factions": user_factions
            })

        result.sort(key=lambda u: u["lastLogin"] or 0, reverse=True)
        self.send_json({"users": result})

    def handle_admin_reset_password(self):
        """POST admin/reset-password"""
        body = self.read_json_body()
        if not body:
            return

        username = body.get('username', '').strip().lower()

        users_file = self.server.data_dir / "users.json"
        users_data = load_json(users_file) or {"users": {}}
        users = users_data.get("users", {})

        if username not in users:
            self.send_error_json("User not found", 404)
            return

        # Set password to "password"
        password = "password"
        salt = secrets.token_bytes(16)
        pw_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 200_000)

        with WRITE_LOCK:
            users[username]["salt"] = salt.hex()
            users[username]["hash"] = pw_hash.hex()
            users[username]["iter"] = 200_000
            atomic_write(users_file, users_data)

        self.send_json({"ok": True})

    def handle_admin_delete(self):
        """POST admin/delete"""
        body = self.read_json_body()
        if not body:
            return

        delete_users = body.get('users', [])
        delete_factions = body.get('factions', [])

        with WRITE_LOCK:
            # Delete factions
            factions_dir = self.server.data_dir / "factions"
            deleted_fids = set()

            for fid in delete_factions:
                if not isinstance(fid, str) or not re.fullmatch(r'[A-Za-z0-9_-]+', fid):
                    continue
                faction_dir = factions_dir / fid
                if faction_dir.exists():
                    import shutil
                    shutil.rmtree(faction_dir)
                    deleted_fids.add(fid)

            # Delete users and their factions
            users_file = self.server.data_dir / "users.json"
            users_data = load_json(users_file) or {"users": {}}
            users = users_data.get("users", {})

            for username in delete_users:
                username_lc = username.lower()
                if username_lc in users:
                    # Find and delete all user's factions
                    if factions_dir.exists():
                        for fid_dir in list(factions_dir.iterdir()):
                            if not fid_dir.is_dir():
                                continue
                            faction_file = fid_dir / "faction.json"
                            if faction_file.exists():
                                faction = load_json(faction_file)
                                if faction.get("owner") == username_lc:
                                    import shutil
                                    shutil.rmtree(fid_dir)
                                    deleted_fids.add(fid_dir.name)

                    # Remove user
                    del users[username_lc]

            atomic_write(users_file, users_data)

            # Garbage collect images
            self.garbage_collect_images(deleted_fids)

        self.send_json({"ok": True})

    def garbage_collect_images(self, deleted_fids: set):
        """Remove unreferenced images."""
        images_dir = self.server.data_dir / "images"
        if not images_dir.exists():
            return

        # Collect all referenced image ids
        referenced = set()
        factions_dir = self.server.data_dir / "factions"

        if factions_dir.exists():
            for fid_dir in factions_dir.iterdir():
                if not fid_dir.is_dir() or fid_dir.name in deleted_fids:
                    continue

                # Scan faction.json
                faction_file = fid_dir / "faction.json"
                if faction_file.exists():
                    self.collect_images_from_json(load_json(faction_file), referenced)

                # Scan version snapshots
                v_dir = fid_dir / "v"
                if v_dir.exists():
                    for v_file in v_dir.iterdir():
                        if v_file.suffix == '.json':
                            self.collect_images_from_json(load_json(v_file), referenced)

        # Delete unreferenced images and update user quotas
        users_file = self.server.data_dir / "users.json"
        users_data = load_json(users_file) or {"users": {}}
        users = users_data.get("users", {})

        for user in users.values():
            user["imageBytes"] = 0

        for image_file in images_dir.iterdir():
            if image_file.name in referenced:
                # Count towards quota (find who uploaded it)
                size = image_file.stat().st_size
                # For simplicity, we can't easily track who uploaded each image
                # So we'll just recalculate based on what they reference
                pass
            else:
                image_file.unlink()

        # Recalculate quotas
        for username in users.keys():
            user_images = self.get_user_images(username, factions_dir, referenced)
            total = sum(images_dir.joinpath(img_id).stat().st_size
                       for img_id in user_images
                       if images_dir.joinpath(img_id).exists())
            users[username]["imageBytes"] = total

        atomic_write(users_file, users_data)

    def collect_images_from_json(self, data: Any, referenced: set):
        """Recursively collect image ids from JSON."""
        if isinstance(data, dict):
            for v in data.values():
                self.collect_images_from_json(v, referenced)
        elif isinstance(data, list):
            for item in data:
                self.collect_images_from_json(item, referenced)
        elif isinstance(data, str):
            # Check if it looks like an image id (sha256.ext)
            if re.match(r'^[a-f0-9]{64}\.(webp|png|jpg)$', data):
                referenced.add(data)

    def get_user_images(self, username: str, factions_dir: Path, all_images: set) -> set:
        """Get images referenced by a user's factions."""
        user_images = set()

        if not factions_dir.exists():
            return user_images

        for fid_dir in factions_dir.iterdir():
            if not fid_dir.is_dir():
                continue
            faction_file = fid_dir / "faction.json"
            if not faction_file.exists():
                continue

            faction = load_json(faction_file)
            if faction.get("owner") != username:
                continue

            # Collect from this faction
            self.collect_images_from_json(faction, user_images)

            # Collect from version snapshots
            v_dir = fid_dir / "v"
            if v_dir.exists():
                for v_file in v_dir.iterdir():
                    if v_file.suffix == '.json':
                        self.collect_images_from_json(load_json(v_file), user_images)

        return user_images

    def handle_admin_requests(self):
        """GET admin/requests?status=..."""
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        status_filter = params.get('status', [''])[0].split(',')
        status_filter = [s.strip() for s in status_filter if s.strip()]

        requests_file = self.server.data_dir / "requests.json"
        requests_data = load_json(requests_file) or {"requests": []}
        requests = requests_data.get("requests", [])

        if status_filter:
            requests = [r for r in requests if r.get("status") in status_filter]

        requests.sort(key=lambda r: r.get("created", 0), reverse=True)
        self.send_json({"requests": requests})

    def handle_admin_update_request(self, rid: str):
        """POST admin/requests/<rid>"""
        body = self.read_json_body()
        if not body:
            return

        status = body.get('status')
        mark = body.get('mark')
        if mark in ('picked', 'started'):
            # Extraction status steps; the request stays open so the checker still lists it
            field = 'pickedUp' if mark == 'picked' else 'startedAt'
            with WRITE_LOCK:
                requests_file = self.server.data_dir / "requests.json"
                requests_data = load_json(requests_file) or {"requests": []}
                request = next((r for r in requests_data.get("requests", []) if r.get("id") == rid), None)
                if not request:
                    self.send_error_json("Request not found", 404)
                    return
                if not request.get(field):
                    request[field] = int(time.time())
                    if mark == 'started' and not request.get('pickedUp'):
                        request['pickedUp'] = request[field]
                    atomic_write(requests_file, requests_data)
            self.send_json(request)
            return
        valid_statuses = ['open', 'notified', 'in_progress', 'done', 'cancelled']
        if status not in valid_statuses:
            self.send_error_json(f"Invalid status. Must be one of: {', '.join(valid_statuses)}")
            return

        with WRITE_LOCK:
            requests_file = self.server.data_dir / "requests.json"
            requests_data = load_json(requests_file) or {"requests": []}
            requests = requests_data.get("requests", [])

            request = next((r for r in requests if r.get("id") == rid), None)
            if not request:
                self.send_error_json("Request not found", 404)
                return

            request["status"] = status
            request["updated"] = int(time.time())

            atomic_write(requests_file, requests_data)
            default = {"in_progress": "Being worked on now.", "notified": "Owner notified.",
                       "done": "Done.", "cancelled": "Cancelled.", "open": "Waiting to be picked up."}
            self.update_terminal_entry(rid, default.get(status, status), only_if_default=True)

        self.send_json(request)

    # ---- Simple Update: fixed numbers pushed straight to the build (no ticker) ----
    # Built factions read their fixed numbers from GET /designer/api/live/<ACR>/values.
    # Each push bumps "rev"; a game pins the rev it started with (?rev=N) so replays never change.
    SIMPLE_UPDATE_FIELDS = {'qty', 'cost', 'effect', 'costB', 'effectB', 'cost2', 'effect2', 'costB2', 'effectB2', 'power', 'aeStart', 'awakenPower', 'dice', 'pains', 'kills', 'num'}

    @staticmethod
    def simple_update_path(section, row_id, field):
        if row_id:
            table = 'units' if section == 'setup' else 'rows'
            return f"{section}.{table}.{row_id}.{field}"
        return f"{section}.{field}"

    def load_live_values(self, fid: str) -> Dict:
        return load_json(self.server.data_dir / "factions" / fid / "live-values.json") or {"rev": 0, "history": []}

    @staticmethod
    def live_overrides(lv: Dict, live_version, rev=None) -> Dict:
        """Pushed values that apply to this live build, up to rev (a rebuild starts clean)."""
        values = {}
        for h in lv.get("history", []):
            if h.get("liveVersion") == live_version and (rev is None or h["rev"] <= rev):
                values[h["path"]] = h["to"]
        return values

    def built_design_with_overrides(self, fid: str, faction: Dict):
        live_version = faction.get("build", {}).get("liveVersion")
        if not live_version:
            return None
        v_file = self.server.data_dir / "factions" / fid / "v" / f"{live_version}.json"
        if not v_file.exists():
            return None
        built = load_json(v_file)
        for path, value in self.live_overrides(self.load_live_values(fid), live_version).items():
            if self.get_path_value(built, path.rsplit('.', 1)[0]) is not None:
                self.set_path_value(built, path, value)
        return built

    def handle_simple_update_push(self, fid: str, faction: Dict, username: str, data: Dict):
        if faction.get("build", {}).get("status") != "built" or not faction["build"].get("liveVersion"):
            self.send_error_json("This faction hasn't been built yet, so there's nothing to update.")
            return
        section, row_id, field = data.get('section'), data.get('rowId'), data.get('field')
        if field not in self.SIMPLE_UPDATE_FIELDS or not isinstance(section, str) or not section.isalnum() \
                or (row_id is not None and not (isinstance(row_id, str) and re.fullmatch(r'[A-Za-z0-9_-]+', row_id))):
            self.send_error_json("That value can't be pushed as a simple update.")
            return
        path = self.simple_update_path(section, row_id, field)
        # The value always comes from the saved design, never from the browser
        value = self.get_path_value(faction["design"], path)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            self.send_error_json("That value isn't a plain number in the design, so it can't be pushed.")
            return
        now = int(time.time())
        with WRITE_LOCK:
            lv_file = self.server.data_dir / "factions" / fid / "live-values.json"
            lv = self.load_live_values(fid)
            built = self.built_design_with_overrides(fid, faction)
            old = self.get_path_value(built, path) if built else None
            lv["rev"] += 1
            lv["history"].append({"rev": lv["rev"], "path": path, "from": old, "to": value, "at": now, "liveVersion": faction["build"]["liveVersion"]})
            atomic_write(lv_file, lv)

            # Logged as an already-done request so the owner can see it in the admin console
            requests_file = self.server.data_dir / "requests.json"
            requests_data = load_json(requests_file) or {"requests": []}
            name = data.get('name') if isinstance(data.get('name'), str) else field
            request = {
                "id": f"r_{secrets.token_urlsafe(6)}", "type": "simple_update", "fid": fid,
                "faction": faction["name"], "acronym": faction["acronym"], "user": username,
                "status": "done", "created": now, "updated": now,
                "text": f"Faction {faction['name']} update, change {section} {name[:100]} fixed value to {value}",
                "data": {"section": section, "rowId": row_id, "field": field, "name": name[:100],
                         "buildValue": old, "designValue": value, "path": path, "rev": lv["rev"]},
            }
            requests_data.setdefault("requests", []).append(request)
            atomic_write(requests_file, requests_data)
        self.send_json(request)

    def handle_live_values(self, acronym: str):
        """GET /designer/api/live/<ACR>/values[?rev=N] - public; read by the homebrew build at game start."""
        from urllib.parse import urlparse, parse_qs
        if not re.fullmatch(r'[A-Z0-9]{2,3}', acronym):
            self.send_error_json("Not found", 404)
            return
        fdir = self.server.data_dir / "factions"
        for d in (fdir.iterdir() if fdir.exists() else []):
            f = load_json(d / "faction.json") if (d / "faction.json").exists() else None
            if f and f.get("acronym") == acronym and f.get("build", {}).get("status") == "built":
                lv = self.load_live_values(d.name)
                q = parse_qs(urlparse(self.path).query)
                rev = lv["rev"]
                if q.get("rev", [""])[0].isdigit():
                    rev = min(int(q["rev"][0]), lv["rev"])
                live = f["build"]["liveVersion"]
                values = self.live_overrides(lv, live, rev)
                self.send_json({"acronym": acronym, "liveVersion": live, "rev": rev, "latestRev": lv["rev"], "values": values})
                return
        self.send_error_json("Not found", 404)

    def handle_admin_get_faction(self, fid: str):
        """GET admin/factions/<fid>"""
        faction = self.load_faction(fid)
        if not faction:
            self.send_error_json("Faction not found", 404)
            return

        self.send_json(faction)

    def handle_admin_view_faction(self, fid: str):
        """GET admin/view-faction/<fid> -- same shape the designer page gets, always read only"""
        faction = self.load_faction(fid)
        if not faction:
            self.send_error_json("Faction not found", 404)
            return

        response = dict(faction)
        response["readOnly"] = True
        response["adminView"] = True
        response["ownerName"] = self.display_name(faction["owner"])
        response["builtDesign"] = self.built_design_with_overrides(fid, faction)
        response["liveValues"] = self.load_live_values(fid)
        response["extractQueue"] = self.extract_queue_position(fid)
        self.send_json(response)

    def handle_admin_patch_faction(self, fid: str):
        """POST admin/factions/<fid>/patch"""
        body = self.read_json_body()
        if not body:
            return

        ops = body.get('ops', [])
        if not isinstance(ops, list):
            self.send_error_json("ops must be an array")
            return

        with WRITE_LOCK:
            faction = self.load_faction(fid)
            if not faction:
                self.send_error_json("Faction not found", 404)
                return

            # Apply ops (same as user patch)
            for op in ops:
                if not self.apply_patch_op(faction, op, fid):
                    return

            faction["updated"] = int(time.time())
            faction_file = self.server.data_dir / "factions" / fid / "faction.json"
            atomic_write(faction_file, faction)

            # Always rewrite current version snapshot
            v_file = self.server.data_dir / "factions" / fid / "v" / f"{faction['current']}.json"
            atomic_write(v_file, faction["design"])

        self.send_json({
            "current": faction["current"],
            "maxVersion": faction["maxVersion"],
            "versions": faction["versions"],
            "session": faction["session"],
            "updated": faction["updated"]
        })

    def handle_admin_build_status(self, fid: str):
        """POST admin/factions/<fid>/build-status"""
        body = self.read_json_body()
        if not body:
            return

        status = body.get('status')
        version = body.get('version')

        valid_statuses = ['in_progress', 'built', 'none']
        if status not in valid_statuses:
            self.send_error_json(f"Invalid status. Must be one of: {', '.join(valid_statuses)}")
            return

        with WRITE_LOCK:
            faction = self.load_faction(fid)
            if not faction:
                self.send_error_json("Faction not found", 404)
                return

            build = faction.setdefault("build", {
                "status": "none",
                "liveVersion": None,
                "requestedAt": None,
                "builtAt": None,
                "history": []
            })

            build["status"] = status

            if status == 'built' and version:
                build["liveVersion"] = version
                build["builtAt"] = int(time.time())

                # Add to history if not already there
                if not any(h.get("version") == version for h in build.get("history", [])):
                    build.setdefault("history", []).append({
                        "version": version,
                        "builtAt": build["builtAt"]
                    })

            faction["updated"] = int(time.time())
            faction_file = self.server.data_dir / "factions" / fid / "faction.json"
            atomic_write(faction_file, faction)

        self.send_json({"ok": True})

    def handle_admin_live_game_versions(self, fid: str):
        """POST admin/factions/<fid>/live-game-versions"""
        body = self.read_json_body()
        if not body:
            return

        versions = body.get('versions', [])
        if not isinstance(versions, list):
            self.send_error_json("versions must be an array")
            return

        with WRITE_LOCK:
            faction = self.load_faction(fid)
            if not faction:
                self.send_error_json("Faction not found", 404)
                return

            faction["liveGameVersions"] = versions
            faction["updated"] = int(time.time())

            faction_file = self.server.data_dir / "factions" / fid / "faction.json"
            atomic_write(faction_file, faction)

        self.send_json({"ok": True})

    def handle_admin_image_usage(self):
        """GET admin/image-usage"""
        images_dir = self.server.data_dir / "images"

        total_bytes = 0
        file_count = 0

        if images_dir.exists():
            for img in images_dir.iterdir():
                if img.is_file():
                    total_bytes += img.stat().st_size
                    file_count += 1

        # Get disk free space
        import shutil
        stat = shutil.disk_usage(self.server.data_dir)

        self.send_json({
            "totalBytes": total_bytes,
            "files": file_count,
            "diskFreeBytes": stat.free
        })

    # ── Helpers ──────────────────────────────────────────────────────────────────

    # ---- Read-only sharing, admin import, Claude terminal log ----

    def display_name(self, username_lc: str) -> str:
        users = (load_json(self.server.data_dir / "users.json") or {}).get("users", {})
        return users.get(username_lc, {}).get("username", username_lc)

    def handle_admin_viewers(self, fid: str):
        """POST admin/factions/<fid>/viewers {viewers:[username...]} -> read-only access for those users"""
        body = self.read_json_body()
        if body is None:
            return
        viewers = body.get('viewers', [])
        if not isinstance(viewers, list):
            self.send_error_json("viewers must be an array")
            return
        users = (load_json(self.server.data_dir / "users.json") or {}).get("users", {})
        viewers = [str(v).strip().lower() for v in viewers]
        missing = [v for v in viewers if v not in users]
        if missing:
            self.send_error_json(f"No such user: {', '.join(missing)}")
            return
        with WRITE_LOCK:
            faction = self.load_faction(fid)
            if not faction:
                self.send_error_json("Faction not found", 404)
                return
            faction["viewers"] = [v for v in dict.fromkeys(viewers) if v != faction["owner"]]
            atomic_write(self.server.data_dir / "factions" / fid / "faction.json", faction)
        self.send_json({"id": fid, "viewers": faction["viewers"]})

    def handle_admin_import_faction(self):
        """POST admin/import-faction {owner, name, acronym, design, built:bool, viewers:[]}
        Creates a design for a user from a faction that already exists in code (no reserved-acronym
        check; still refuses an acronym another design uses). built=true marks version 1 as the live build."""
        body = self.read_json_body()
        if body is None:
            return
        owner = str(body.get('owner', '')).strip().lower()
        name = str(body.get('name', '')).strip()
        acronym = str(body.get('acronym', '')).strip().upper()
        design = body.get('design')
        users = (load_json(self.server.data_dir / "users.json") or {}).get("users", {})
        if owner not in users:
            self.send_error_json("No such user")
            return
        if len(name) < 5 or not re.match(r'^[A-Z0-9]{2,3}$', acronym):
            self.send_error_json("Name must be 5+ characters and acronym 2-3 letters or digits")
            return
        base = self.new_design()
        if not isinstance(design, dict) or set(design) - set(base):
            self.send_error_json("design must be an object with only the known sections")
            return
        for key, value in base.items():
            design.setdefault(key, value)
        viewers = [str(v).strip().lower() for v in body.get('viewers', [])]
        if any(v not in users for v in viewers):
            self.send_error_json("A viewer is not a user")
            return
        factions_dir = self.server.data_dir / "factions"
        factions_dir.mkdir(parents=True, exist_ok=True)
        now = int(time.time())
        fid = secrets.token_urlsafe(9).replace('_', '').replace('-', '').lower()[:12]
        built = bool(body.get('built'))
        faction = {
            "id": fid, "owner": owner, "name": name, "acronym": acronym,
            "created": now, "updated": now, "current": 1, "maxVersion": 1,
            "versions": [{"n": 1, "from": None, "sections": [k for k in base if not self.is_section_empty(k, design.get(k))],
                          "created": now, "deleted": False}],
            "session": {"n": 1, "sections": [], "last": 0},
            "build": {"status": "built" if built else "none", "liveVersion": 1 if built else None,
                      "requestedAt": None, "builtAt": now if built else None,
                      "history": [{"version": 1, "builtAt": now}] if built else []},
            "liveGameVersions": [],
            "viewers": [v for v in viewers if v != owner],
            "imported": True,
            "design": design
        }
        with WRITE_LOCK:
            for fd in factions_dir.iterdir():
                if (fd / "faction.json").exists() and load_json(fd / "faction.json").get("acronym") == acronym:
                    self.send_error_json(f"Acronym {acronym} is already used by another design")
                    return
            (factions_dir / fid / "v").mkdir(parents=True, exist_ok=True)
            atomic_write(factions_dir / fid / "faction.json", faction)
            atomic_write(factions_dir / fid / "v" / "1.json", design)
        self.send_json(faction)

    @staticmethod
    def terminal_type(request: Dict) -> str:
        t = request.get("type")
        if t == "extract":
            return "design menu" if request.get("data", {}).get("target") == "menus" else "design extraction"
        if t == "bug":
            return "design bug fix"
        return "design build"   # build and update both change the built faction

    def add_terminal_entry(self, kind: str, user: str, prompt: str, summary: str, ref: Optional[str] = None) -> Dict:
        """Append one row to terminal-log.json. Caller may already hold WRITE_LOCK (it is not re-entrant),
        so this uses its own lock."""
        entry = {"id": ref or f"t_{secrets.token_urlsafe(6)}", "at": int(time.time()), "type": kind,
                 "user": user, "prompt": str(prompt)[:20000], "summary": str(summary)[:20000], "defaultSummary": True}
        with TERMINAL_LOCK:
            path = self.server.data_dir / "terminal-log.json"
            log = load_json(path) or {"entries": []}
            log.setdefault("entries", []).append(entry)
            number_terminal_entries(log)
            log["entries"] = log["entries"][-2000:]
            atomic_write(path, log)
        return entry

    def update_terminal_entry(self, entry_id: str, summary: str, only_if_default: bool = False) -> Optional[Dict]:
        with TERMINAL_LOCK:
            path = self.server.data_dir / "terminal-log.json"
            log = load_json(path) or {"entries": []}
            entry = next((e for e in log.get("entries", []) if e.get("id") == entry_id), None)
            if not entry or (only_if_default and not entry.get("defaultSummary")):
                return entry
            entry["summary"] = str(summary)[:20000]
            entry["defaultSummary"] = only_if_default
            entry["updatedAt"] = int(time.time())
            atomic_write(path, log)
        return entry

    def handle_admin_terminal_log(self, entry_id: Optional[str]):
        """POST admin/terminal-log {type,user,prompt,summary,[id],[at]} adds a row;
        POST admin/terminal-log/<id> {summary} replaces that row's summary."""
        body = self.read_json_body()
        if body is None:
            return
        if entry_id:
            entry = self.update_terminal_entry(entry_id, body.get('summary', ''))
            if not entry:
                self.send_error_json("Entry not found", 404)
                return
            self.send_json(entry)
            return
        kinds = ['admin', 'design extraction', 'design menu', 'design build', 'design bug fix']
        if body.get('type') not in kinds:
            self.send_error_json(f"type must be one of: {', '.join(kinds)}")
            return
        entry = self.add_terminal_entry(body['type'], str(body.get('user') or 'admin'), body.get('prompt', ''),
                                        body.get('summary', ''), ref=body.get('id'))
        if isinstance(body.get('at'), int):
            with TERMINAL_LOCK:
                path = self.server.data_dir / "terminal-log.json"
                log = load_json(path)
                for e in log["entries"]:
                    if e["id"] == entry["id"]:
                        e["at"] = body["at"]
                atomic_write(path, log)
        self.send_json(entry)

    def load_faction(self, fid: str) -> Optional[Dict]:
        """Load faction by ID."""
        faction_file = self.server.data_dir / "factions" / fid / "faction.json"
        if not faction_file.exists():
            return None
        return load_json(faction_file)

    def new_design(self) -> Dict:
        """Create a blank design with defaults."""
        design = {
            "meta": {"color": None},
            "card": {"image": None, "glyph": None},
            "sbImages": {"mode": None, "all": None, "each": [None]*6},
            "sbImagesB": {"mode": None, "all": None, "each": [None]*6},
            "ae": {
                "enabled": False,
                "name": "",
                "acronym": "",
                "rows": [{"id": self.new_id(), "sign": "+", "kind": "fixed", "qty": None, "calc": "", "desc": ""}]
            },
            "ufa": {
                "name": "",
                "phase": None,
                "type": None,
                "hasCost": False,
                "cost": None,
                "hasEffect": False,
                "effect": None,
                "text": ""
            },
            "setup": {
                "text": "",
                "location": None,
                "earthRegion": None,
                "libraryRegion": None,
                "constraints": {
                    "follows": None,
                    "water": True,
                    "land": True,
                    "emptyFactionGlyph": True,
                    "thorn": True,
                    "dragon": True,
                    "chevron": True,
                    "noneOf3": True,
                    "proximity": "N/A",
                    "custom": ""
                },
                "gate": None,
                "units": [{"id": self.new_id(), "onMap": True, "name": "", "qty": None}],
                "power": 8,
                "aeStart": 0
            },
            "units": {"rows": [self.blank_unit(), self.blank_unit(), self.blank_unit()]},
            "sbr": {"multiText": "", "rows": [
                {"id": self.new_id(), "text": "", "hasNum": False, "num": None} for _ in range(6)
            ]},
            "sb": {"twoSided": False, "rows": [
                {"id": self.new_id(), "name": "", "type": None, "cost": 0, "hasEffect": False, "effect": None, "text": "",
                 "nameB": "", "typeB": None, "costB": 0, "hasEffectB": False, "effectB": None, "textB": "",
                 "dual": False, "name2": "", "type2": None, "cost2": 0, "hasEffect2": False, "effect2": None, "text2": "",
                 "dualB": False, "nameB2": "", "typeB2": None, "costB2": 0, "hasEffectB2": False, "effectB2": None,
                 "textB2": ""} for _ in range(6)
            ]},
            # Each table starts with one blank row (same as Rules.newDesign in www/rules.js)
            "region": {"rows": [{"id": self.new_id(), "name": "", "image": None, "restrictions": "", "adjacency": ""}]},
            "tokens": {"rows": [{"id": self.new_id(), "name": "", "qty": None, "image": None, "placement": "",
                                 "effects": "", "hasEffect": False, "effect": None}]},
            "custom": {"rows": [{"id": self.new_id(), "name": "", "image": None, "placement": "", "usage": "",
                                 "effects": "", "hasNum": False, "num": None}]},
            "menus": {"rows": [{"id": self.new_id(), "name": "", "section": None, "item": None, "prompted": None,
                                "title": "", "hasSubtitle": False, "subtitle": "", "button": "", "cancel": False,
                                "skip": False, "done": False, "multiSelect": False, "repeat": False, "repeatCount": "",
                                "numberPick": False, "numberMin": "", "numberMax": "", "greyedOptions": False,
                                "greyedReason": "", "infoOnly": False, "confirm": False, "confirmText": "",
                                "showPicked": False, "leadsToNext": False, "next": None, "nextTrigger": ""}]}
        }
        # Every design section ends with a free "Any custom logic or rules" box
        for key in ("ae", "ufa", "setup", "units", "sbr", "sb", "region", "tokens", "custom"):
            design[key]["customLogic"] = ""
        return design

    def blank_unit(self) -> Dict:
        """Create a blank unit row."""
        return {
            "id": self.new_id(),
            "type": None,
            "name": "",
            "mapImage": None,
            "mapScale": 1.0,
            "silhouette": None,
            "qty": None,
            "costType": None,
            "cost": None,
            "costCalc": "",
            "awakenReq": "",
            "awakenPower": None,
            "awakenRegion": "",
            "combatType": None,
            "dice": None,
            "diceCalc": "",
            "pains": None,
            "kills": None,
            "resultsCalc": "",
            "relatedSb": [],
            "relatedSbNames": [],
            "abilityName": "",
            "abilityText": ""
        }

    def new_id(self) -> str:
        """Generate an 8-character random ID."""
        return secrets.token_urlsafe(6)[:8]


def main():
    parser = argparse.ArgumentParser(description='CW Faction Designer Server')
    parser.add_argument('--data', required=True, help='Data directory path')
    parser.add_argument('--port', type=int, default=8091, help='Port to listen on')
    parser.add_argument('--host', default='127.0.0.1', help='Host to bind to')
    parser.add_argument('--token-hash-file', required=True, help='Admin token hash file')
    parser.add_argument('--reference', default='', help='Path to reference.json')

    args = parser.parse_args()

    data_dir = Path(args.data)
    data_dir.mkdir(parents=True, exist_ok=True)

    # Load reserved acronyms
    reserved = DEFAULT_RESERVED_ACRONYMS
    if args.reference and Path(args.reference).exists():
        try:
            with open(args.reference, 'r') as f:
                ref = json.load(f)
                reserved = ref.get('reservedAcronyms', DEFAULT_RESERVED_ACRONYMS)
        except Exception:
            pass

    # Create server
    server = ThreadingHTTPServer((args.host, args.port), FactionDesignerHandler)
    server.data_dir = data_dir
    server.admin_token_hash_file = Path(args.token_hash_file)
    server.reserved_acronyms = reserved

    print(f"CW Faction Designer Server running on {args.host}:{args.port}", file=sys.stderr)
    print(f"Data directory: {data_dir}", file=sys.stderr)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...", file=sys.stderr)
        server.shutdown()


if __name__ == '__main__':
    main()
