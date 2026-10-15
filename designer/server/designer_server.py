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


def compute_spellbook_guidance(design: Dict) -> str:
    """Compute guidance for Claude about multi-power and multi-sided spellbooks."""
    sb = design.get('sb', {})
    rows = sb.get('rows', [])

    # Check for multi-sided spellbooks
    has_multi_sided = any(row.get('twoSided') for row in rows)

    # Check for multi-power spellbooks
    has_multi_power = False
    for row in rows:
        # Check side A
        if row.get('dual'):
            has_multi_power = True
            break
        # Check side B
        if row.get('twoSided') and row.get('dualB'):
            has_multi_power = True
            break

    if not has_multi_power and not has_multi_sided:
        return ''

    guidance = ''

    if has_multi_power:
        guidance += 'MULTI-POWER SPELLBOOKS:\n'
        guidance += '- Spellbooks with multiple powers on 1 spellbook side = treated as a single spellbook\n'
        guidance += '- Completing single SBR earns a SB with 2 powers = still ONE spellbook, earn BOTH powers at once\n'
        guidance += '- Both powers earned, blocked, and copied together (Moonbeast blocks BOTH)\n'
        guidance += '- Max 6 SBR/SB slots on faction card (unless explicitly told otherwise)\n'
        guidance += '- Spellbook overlays must describe BOTH powers\n'
        guidance += '- Moonbeast blocking a 2-power spellbook blocks BOTH powers\n'
        guidance += '- Copying a spellbook (e.g., Nodens) copies BOTH powers\n'

    if has_multi_sided:
        if has_multi_power:
            guidance += '\n'
        guidance += 'MULTI-SIDED SPELLBOOKS:\n'
        guidance += '- 2 sides with powers = 2 connected spellbooks, NOT 2 independent ones\n'
        guidance += '- Sides swap per that spellbook\'s explicit rules, not taken independently\n'
        guidance += '- Leverage "Recriminations" pattern to code swaps (strictly apply so only "sides" of same SB swap via this faction\'s mechanism)\n'
        guidance += '- 3rd "face down" side can be: use-once (Dragon Ascending pattern) OR recharge (Doom Phase or other)\n'
        guidance += '- Recharge determines whether flipped back to side A or side B (consult spellbook rules; not automatic)\n'

    return guidance


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

        # Public endpoint for stability
        if path == '/designer/api/public/stability':
            self.handle_public_stability()
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

        # Neutral units (stand-alone, not part of any faction)
        if path == '/designer/api/units':
            self.handle_list_units()
            return
        m = re.fullmatch(r'/designer/api/units/([A-Za-z0-9_-]+)', path)
        if m:
            self.handle_get_unit(m.group(1))
            return

        # Maps
        if path == '/designer/api/maps':
            self.handle_list_maps()
            return
        if path.startswith('/designer/api/maps/'):
            parts = path.split('/')
            if len(parts) >= 5:
                mid = parts[4]
                if len(parts) == 5:
                    self.handle_get_map(mid)
                    return
                elif len(parts) == 6 and parts[5] == 'requests':
                    self.handle_get_map_requests(mid)
                    return
                elif len(parts) == 6 and parts[5] == 'extract-queue':
                    self.handle_get_map_extract_queue(mid)
                    return

        # Admin endpoints
        m = re.fullmatch(r'/designer/api/live/([A-Za-z0-9]{2,3})/values', path)
        if m:
            self.handle_live_values(m.group(1))
            return

        # Terminal log history for one design, used by the faction/unit/map "Bug Report" screen
        if path == '/designer/api/terminal-log':
            self.handle_terminal_log()
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

        # Neutral unit endpoints
        if path == '/designer/api/units':
            self.handle_create_unit()
            return
        m = re.fullmatch(r'/designer/api/units/([A-Za-z0-9_-]+)/patch', path)
        if m:
            self.handle_patch_unit(m.group(1))
            return
        m = re.fullmatch(r'/designer/api/units/([A-Za-z0-9_-]+)/copy', path)
        if m:
            self.handle_copy_unit(m.group(1))
            return
        m = re.fullmatch(r'/designer/api/units/([A-Za-z0-9_-]+)/rename', path)
        if m:
            self.handle_rename_unit(m.group(1))
            return
        m = re.fullmatch(r'/designer/api/units/([A-Za-z0-9_-]+)/close-session', path)
        if m:
            self.handle_close_unit_session(m.group(1))
            return
        m = re.fullmatch(r'/designer/api/units/([A-Za-z0-9_-]+)/rollback', path)
        if m:
            self.handle_rollback_unit(m.group(1))
            return
        m = re.fullmatch(r'/designer/api/units/([A-Za-z0-9_-]+)/delete-version', path)
        if m:
            self.handle_delete_unit_version(m.group(1))
            return
        m = re.fullmatch(r'/designer/api/units/([A-Za-z0-9_-]+)/answers', path)
        if m:
            self.handle_submit_answers(m.group(1), 'unit')
            return
        m = re.fullmatch(r'/designer/api/units/([A-Za-z0-9_-]+)/request', path)
        if m:
            self.handle_create_unit_request(m.group(1))
            return
        m = re.fullmatch(r'/designer/api/units/([A-Za-z0-9_-]+)/rollback', path)
        if m:
            self.handle_rollback_unit(m.group(1))
            return
        m = re.fullmatch(r'/designer/api/units/([A-Za-z0-9_-]+)/delete-version', path)
        if m:
            self.handle_delete_unit_version(m.group(1))
            return

        # Map endpoints
        if path == '/designer/api/maps':
            self.handle_create_map()
            return
        if path.startswith('/designer/api/maps/'):
            parts = path.split('/')
            if len(parts) >= 5:
                mid = parts[4]
                if len(parts) == 6:
                    action = parts[5]
                    if action == 'patch':
                        self.handle_patch_map(mid)
                        return
                    elif action == 'close-session':
                        self.handle_close_map_session(mid)
                        return
                    elif action == 'rollback':
                        self.handle_rollback_map(mid)
                        return
                    elif action == 'delete-version':
                        self.handle_delete_map_version(mid)
                        return
                    elif action == 'request':
                        self.handle_create_map_request(mid)
                        return
                    elif action == 'answers':
                        self.handle_submit_map_answers(mid)
                        return
                    elif action == 'copy':
                        self.handle_copy_map(mid)
                        return
                    elif action == 'rename':
                        self.handle_rename_map(mid)
                        return

        if path.startswith('/designer/api/factions/'):
            parts = path.split('/')
            if len(parts) >= 5:
                fid = parts[4]
                if len(parts) == 6:
                    action = parts[5]
                    if action == 'stability':
                        self.handle_set_stability(fid)
                        return
                    elif action == 'copy':
                        self.handle_copy_faction(fid)
                        return
                    elif action == 'rename':
                        self.handle_rename_faction(fid)
                        return
                    elif action == 'patch':
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
                    elif action == 'answers':
                        self.handle_submit_answers(fid, 'faction')
                        return

        # Unit answers endpoint
        m = re.fullmatch(r'/designer/api/units/([A-Za-z0-9_-]+)/answers', path)
        if m:
            self.handle_submit_answers(m.group(1), 'unit')
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

        # Reserved system owner name for base factions
        if username.lower() == 'base':
            self.send_error_json("Username 'base' is reserved")
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
        base_factions = []

        if factions_dir.exists():
            for fid_dir in factions_dir.iterdir():
                if not fid_dir.is_dir():
                    continue
                faction_file = fid_dir / "faction.json"
                if not faction_file.exists():
                    continue
                faction = load_json(faction_file)

                # Base factions: owned by "base" system user, visible to everyone read-only (except cavysupreme)
                if faction.get("base") or faction.get("owner") == "base":
                    base_item = {
                        "id": faction["id"],
                        "name": faction["name"],
                        "acronym": faction["acronym"],
                        "current": faction["current"],
                        "buildStatus": faction.get("build", {}).get("status", "none"),
                        "updated": faction["updated"],
                        "base": True,
                        "owner": "base",
                        "ownerName": "Base Faction"
                    }
                    if username != "cavysupreme":
                        base_item["readOnly"] = True
                    base_factions.append(base_item)
                elif faction.get("owner") == username:
                    factions.append({
                        "id": faction["id"],
                        "name": faction["name"],
                        "acronym": faction["acronym"],
                        "current": faction["current"],
                        "buildStatus": faction.get("build", {}).get("status", "none"),
                        "updated": faction["updated"]
                    })
                elif username in faction.get("editors", []):
                    # Shared with this user with edit access (set by the admin)
                    factions.append({
                        "id": faction["id"],
                        "name": faction["name"],
                        "acronym": faction["acronym"],
                        "current": faction["current"],
                        "buildStatus": faction.get("build", {}).get("status", "none"),
                        "updated": faction["updated"],
                        "owner": faction["owner"],
                        "ownerName": self.display_name(faction["owner"])
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

        # Sort base factions by acronym: GC, CC, BG, YS
        base_order = {"GC": 0, "CC": 1, "BG": 2, "YS": 3}
        base_factions.sort(key=lambda f: base_order.get(f["acronym"], 99))

        # Combine: user's own factions, then shared, then base
        self.send_json({"factions": factions + base_factions})

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
            "adminNotes": "",
            "bugHistory": [],
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

    # ── Neutral units ─────────────────────────────────────────────────────────────
    # Stored apart from factions in data/units/<uid>/unit.json. The design is shaped like a faction
    # design cut down to one unit ({"meta", "units": {"rows": [UNIT], "customLogic"}}), so the same
    # Units form edits it. No versions: changes save in place.

    def units_dir(self) -> Path:
        return self.server.data_dir / "units"

    def load_unit(self, uid: str) -> Optional[Dict]:
        f = self.units_dir() / uid / "unit.json"
        return load_json(f) if f.exists() else None

    def iter_units(self):
        d = self.units_dir()
        if d.exists():
            for u_dir in d.iterdir():
                f = u_dir / "unit.json"
                if u_dir.is_dir() and f.exists():
                    yield u_dir, load_json(f)

    def maps_dir(self) -> Path:
        return self.server.data_dir / "maps"

    def load_map(self, mid: str) -> Optional[Dict]:
        f = self.maps_dir() / mid / "map.json"
        return load_json(f) if f.exists() else None

    def iter_maps(self):
        d = self.maps_dir()
        if d.exists():
            for m_dir in d.iterdir():
                f = m_dir / "map.json"
                if m_dir.is_dir() and f.exists():
                    yield m_dir, load_json(f)

    def new_neutral_design(self) -> Dict:
        row = self.blank_unit()
        row.pop("relatedSb", None)       # spellbooks belong to a faction
        row.pop("relatedSbNames", None)
        return {"meta": {"color": None, "adminNotes": ""}, "units": {"rows": [row], "customLogic": "", "adminNotes": ""}}

    def new_map_design(self) -> Dict:
        """Create a blank map design matching frontend schema (rules.js newMapDesign)."""
        return {
            "images": {
                "items": [],  # NOT "images"
                "layout": {"type": None, "columns": 2, "order": [], "notes": ""},  # NOT null at top level
                "regions": {"rows": []},  # NOT just []
                "customLogic": "",
                "adminNotes": ""
            },
            "bitmaps": {
                "items": [],
                "customLogic": "",
                "adminNotes": ""
            },
            "adjacency": {
                "cols": 32,
                "rows": 16,
                "cells": [],
                "special": {"rows": []},  # NOT "specialTypes"
                "customLogic": "",
                "adminNotes": ""
            },
            "units": {
                "wikiUrl": "",
                "rows": [],
                "customLogic": "",
                "adminNotes": ""
            },
            "tokens": {
                "rows": [],
                "customLogic": "",
                "adminNotes": ""
            },
            "sb": {
                "requirements": {"rows": []},  # NOT "multiText" + "rows"
                "books": {"rows": []},  # NOT just "books"
                "customLogic": "",
                "adminNotes": ""
            },
            "glyphs": {
                "rows": [],
                "customLogic": "",
                "adminNotes": ""
            },
            "abilities": {
                "rows": [],
                "customLogic": "",
                "adminNotes": ""
            }
        }

    def blank_map_row(self, table_path: str) -> Dict:
        """Create a blank row for a map table (matches rules.js blankMapRow)."""
        row_id = self.new_id()
        if table_path == "images.items":
            return {"id": row_id, "label": "", "image": None}
        elif table_path == "images.regions.rows":
            return {"id": row_id, "name": "", "type": "Land", "glyphs": {"gc": False, "cc": False, "bg": False, "ys": False, "dragon": False, "chevron": False, "thorn": False}}
        elif table_path == "bitmaps.items":
            return {"id": row_id, "image": None, "colors": {}, "centroids": {}}
        elif table_path == "adjacency.special.rows":
            return {"id": row_id, "name": "", "desc": "", "cost": None, "oneWay": False, "pairs": []}
        elif table_path == "adjacency.special.rows.pairs":
            return {"id": row_id, "from": None, "to": None}
        elif table_path == "units.rows":
            unit = self.blank_unit()
            unit.pop("relatedSb", None)
            unit.pop("relatedSbNames", None)
            return unit
        elif table_path == "tokens.rows":
            return {"id": row_id, "name": "", "qty": None, "image": None, "placement": "", "effects": "", "hasEffect": False, "effect": None}
        elif table_path == "sb.requirements.rows":
            return {"id": row_id, "text": "", "hasNum": False, "num": None}
        elif table_path == "sb.books.rows":
            return {"id": row_id, "name": "", "type": None, "cost": 0, "hasEffect": False, "effect": None, "text": ""}
        elif table_path == "glyphs.rows":
            return {"id": row_id, "name": "", "image": None, "desc": ""}
        elif table_path == "abilities.rows":
            return {"id": row_id, "name": "", "when": None, "type": None, "cost": None, "who": "", "text": ""}
        return {"id": row_id}

    def unit_summary(self, unit: Dict) -> Dict:
        row = (unit.get("design", {}).get("units", {}).get("rows") or [{}])[0]
        return {"id": unit["id"], "name": row.get("name") or "", "type": row.get("type"),
                "created": unit["created"], "updated": unit["updated"],
                "buildStatus": unit.get("build", {}).get("status", "none")}

    def handle_list_units(self):
        """GET /designer/api/units"""
        username = self.verify_session()
        if not username:
            self.send_error_json("Unauthorized", 401)
            return
        units = [self.unit_summary(u) for _, u in self.iter_units() if u.get("owner") == username]
        units.sort(key=lambda u: u["updated"], reverse=True)
        self.send_json({"units": units})

    def handle_create_unit(self):
        """POST /designer/api/units {name}"""
        username = self.verify_session()
        if not username:
            self.send_error_json("Unauthorized", 401)
            return
        body = self.read_json_body()
        if body is None:
            return
        name = str(body.get('name', '')).strip()
        if not name or len(name) > 60:
            self.send_error_json("Unit name must be 1-60 characters")
            return
        now = int(time.time())
        design = self.new_neutral_design()
        design["units"]["rows"][0]["name"] = name
        with WRITE_LOCK:
            uid = self.new_id()
            while (self.units_dir() / uid).exists() or not re.fullmatch(r'[A-Za-z0-9_-]+', uid):
                uid = self.new_id()
            unit = {
                "id": uid,
                "owner": username,
                "created": now,
                "updated": now,
                "adminNotes": "",
                "bugHistory": [],
                "design": design,
                "build": {"status": "none", "liveVersion": None, "requestedAt": None, "builtAt": None}
            }
            (self.units_dir() / uid).mkdir(parents=True, exist_ok=True)
            atomic_write(self.units_dir() / uid / "unit.json", unit)
        self.send_json(unit)

    def handle_get_unit(self, uid: str):
        """GET /designer/api/units/<uid>"""
        username = self.verify_session()
        if not username:
            self.send_error_json("Unauthorized", 401)
            return
        unit = self.load_unit(uid)
        if not unit:
            self.send_error_json("Unit not found", 404)
            return
        if unit.get("owner") != username:
            self.send_error_json("Forbidden", 403)
            return
        # Migrate old units without build field
        if "build" not in unit:
            unit["build"] = {"status": "none", "liveVersion": None, "requestedAt": None, "builtAt": None}
        # Migrate to version system (lazy migration)
        now = int(time.time())
        if "current" not in unit:
            unit["current"] = 1
            unit["maxVersion"] = 1
            unit["versions"] = [{"n": 1, "from": None, "sections": ["unit"], "created": unit.get("created", now), "deleted": False}]
            unit["session"] = {"n": 1, "sections": [], "last": 0}
            # Create v/ directory and save initial version
            v_dir = self.units_dir() / uid / "v"
            v_dir.mkdir(exist_ok=True)
            atomic_write(v_dir / "1.json", unit["design"])
        # Add buildAttempted flag
        unit["buildAttempted"] = self.has_build_attempt(unit, uid, "unit")
        # Include claudeQA if it exists
        if "claudeQA" not in unit:
            unit["claudeQA"] = {}
        # Ensure bugHistory exists
        if "bugHistory" not in unit:
            unit["bugHistory"] = []
        self.send_json(unit)

    def handle_copy_unit(self, uid: str):
        """POST /designer/api/units/<uid>/copy - Create a duplicate of this unit"""
        username = self.verify_session()
        if not username:
            self.send_error_json("Unauthorized", 401)
            return

        with WRITE_LOCK:
            unit = self.load_unit(uid)
            if not unit:
                self.send_error_json("Unit not found", 404)
                return

            if unit.get("owner") != username:
                self.send_error_json("Forbidden", 403)
                return

            # Generate new ID
            new_uid = self.new_id()
            while (self.units_dir() / new_uid).exists():
                new_uid = self.new_id()

            # Get the unit name and create new one with "Copy of" prefix
            unit_name = unit.get("design", {}).get("units", {}).get("rows", [{}])[0].get("name", "Unnamed Unit")
            now = int(time.time())

            # Create new design and set the copied name
            new_design = json.loads(json.dumps(unit["design"]))  # Deep copy
            if new_design.get("units", {}).get("rows"):
                new_design["units"]["rows"][0]["name"] = f"Copy of {unit_name}"

            new_unit = {
                "id": new_uid,
                "owner": username,
                "created": now,
                "updated": now,
                "adminNotes": "",
                "bugHistory": [],
                "design": new_design,
                "build": {"status": "none", "liveVersion": None, "requestedAt": None, "builtAt": None},
                "current": 1,
                "maxVersion": 1,
                "versions": [{"n": 1, "from": None, "sections": ["unit"], "created": now, "deleted": False}],
                "session": {"n": 1, "sections": [], "last": now}
            }

            # Create unit directory and save
            (self.units_dir() / new_uid).mkdir(parents=True, exist_ok=True)
            v_dir = self.units_dir() / new_uid / "v"
            v_dir.mkdir(exist_ok=True)
            atomic_write(self.units_dir() / new_uid / "unit.json", new_unit)
            atomic_write(v_dir / "1.json", new_design)

        self.send_json(new_unit)

    def handle_rename_unit(self, uid: str):
        """POST /designer/api/units/<uid>/rename {name} - Update unit name"""
        username = self.verify_session()
        if not username:
            self.send_error_json("Unauthorized", 401)
            return

        body = self.read_json_body()
        if not body:
            return

        new_name = body.get('name', '').strip()

        if not new_name or len(new_name) > 60:
            self.send_error_json("Unit name must be 1-60 characters")
            return

        with WRITE_LOCK:
            unit = self.load_unit(uid)
            if not unit:
                self.send_error_json("Unit not found", 404)
                return

            if unit.get("owner") != username:
                self.send_error_json("Forbidden", 403)
                return

            # Update unit name in design
            if unit.get("design", {}).get("units", {}).get("rows"):
                unit["design"]["units"]["rows"][0]["name"] = new_name

            unit["updated"] = int(time.time())
            atomic_write(self.units_dir() / uid / "unit.json", unit)

        self.send_json({"ok": True, "name": new_name})

    def handle_patch_unit(self, uid: str):
        """POST /designer/api/units/<uid>/patch {ops: [{op: "set", path, value}]}"""
        username = self.verify_session()
        if not username:
            self.send_error_json("Unauthorized", 401)
            return
        body = self.read_json_body()
        if body is None:
            return
        ops = body.get('ops', [])
        if not isinstance(ops, list):
            self.send_error_json("ops must be an array")
            return
        with WRITE_LOCK:
            unit = self.load_unit(uid)
            if not unit:
                self.send_error_json("Unit not found", 404)
                return
            if unit.get("owner") != username:
                self.send_error_json("Forbidden", 403)
                return

            # Ensure unit has version system
            now = int(time.time())
            if "current" not in unit:
                unit["current"] = 1
                unit["maxVersion"] = 1
                unit["versions"] = [{"n": 1, "from": None, "sections": ["unit"], "created": unit.get("created", now), "deleted": False}]
                unit["session"] = {"n": 1, "sections": [], "last": 0}

            design = unit["design"]
            row_id = design["units"]["rows"][0]["id"]

            for op in ops:
                path = op.get('path', '') if isinstance(op, dict) else ''
                # One unit only: no added or deleted rows, and only that unit's fields (or the custom logic box)
                # Allow nested spellbook fields: units.rows.<id>.spellbook (the whole object), .spellbook.enabled, .spellbook.requirement.text, etc.
                ok = op.get('op') == 'set' and (
                    path == 'units.customLogic' or
                    re.fullmatch(r'units\.rows\.' + re.escape(row_id) + r'\.[A-Za-z0-9]+', path) or
                    re.fullmatch(r'units\.rows\.' + re.escape(row_id) + r'\.spellbook', path) or
                    re.fullmatch(r'units\.rows\.' + re.escape(row_id) + r'\.spellbook\.[A-Za-z0-9]+', path) or
                    re.fullmatch(r'units\.rows\.' + re.escape(row_id) + r'\.spellbook\.(requirement|book)\.[A-Za-z0-9]+', path))
                if not ok:
                    self.send_error_json("Invalid change for a unit")
                    return

                # Apply version logic (simplified for single-section unit)
                section = "unit"
                is_addition = self.is_unit_addition(unit, op)

                current = unit["current"]
                max_version = unit["maxVersion"]
                live_version = unit.get("build", {}).get("liveVersion")
                is_locked = current < max_version or current == live_version

                session = unit["session"]
                session_open = (
                    session["n"] == current and
                    time.time() - session["last"] < 600 and
                    section in session["sections"]
                )

                if is_locked:
                    self.create_new_unit_version(unit, section, uid)
                elif is_addition:
                    pass  # Apply in place
                elif not session_open:
                    self.create_new_unit_version(unit, section, uid)

                self.set_path_value(design, path, op.get('value'))

                # Update session
                session["last"] = now
                if session["n"] == unit["current"]:
                    if section not in session["sections"]:
                        session["sections"].append(section)
                else:
                    session["n"] = unit["current"]
                    session["sections"] = [section]

                # Add section to current version's sections if not present
                for v in unit["versions"]:
                    if v["n"] == unit["current"]:
                        if section not in v["sections"]:
                            v["sections"].append(section)
                        break

            unit["updated"] = now
            atomic_write(self.units_dir() / uid / "unit.json", unit)

            # Always rewrite current version snapshot
            v_dir = self.units_dir() / uid / "v"
            v_dir.mkdir(exist_ok=True)
            v_file = v_dir / f"{unit['current']}.json"
            atomic_write(v_file, unit["design"])

        self.send_json({
            "current": unit["current"],
            "maxVersion": unit["maxVersion"],
            "versions": unit["versions"],
            "session": unit["session"],
            "updated": unit["updated"]
        })

    def is_unit_addition(self, unit: Dict, op: Dict) -> bool:
        """Check if operation is an addition (empty→non-empty) for a unit."""
        if op.get('op') != 'set':
            return False
        path = op.get('path', '')
        value = op.get('value')
        design = unit["design"]
        current = self.get_path_value(design, path)
        current_empty = current in ("", None, [])
        value_empty = value in ("", None, [])
        return current_empty and not value_empty

    def create_new_unit_version(self, unit: Dict, section: str, uid: str):
        """Create a new version and freeze the current one for a unit."""
        current = unit["current"]
        max_version = unit["maxVersion"]

        # Freeze current version
        v_dir = self.units_dir() / uid / "v"
        v_dir.mkdir(exist_ok=True)
        v_file = v_dir / f"{current}.json"
        if not v_file.exists():
            atomic_write(v_file, unit["design"])

        # Create new version
        new_n = max_version + 1
        now = int(time.time())

        unit["versions"].append({
            "n": new_n,
            "from": current,
            "sections": [section],
            "created": now,
            "deleted": False
        })

        unit["current"] = new_n
        unit["maxVersion"] = new_n
        unit["session"] = {"n": new_n, "sections": [section], "last": now}

    def handle_close_unit_session(self, uid: str):
        """POST /designer/api/units/<uid>/close-session"""
        username = self.verify_session()
        if not username:
            self.send_error_json("Unauthorized", 401)
            return

        with WRITE_LOCK:
            unit = self.load_unit(uid)
            if not unit:
                self.send_error_json("Unit not found", 404)
                return

            if unit.get("owner") != username:
                self.send_error_json("Forbidden", 403)
                return

            # Clear session by resetting last time to far past
            if "session" not in unit:
                unit["session"] = {"n": 1, "sections": [], "last": 0}
            unit["session"]["last"] = 0
            unit_file = self.units_dir() / uid / "unit.json"
            atomic_write(unit_file, unit)

        self.send_json({})

    def handle_rollback_unit(self, uid: str):
        """POST /designer/api/units/<uid>/rollback"""
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
            unit = self.load_unit(uid)
            if not unit:
                self.send_error_json("Unit not found", 404)
                return

            if unit.get("owner") != username:
                self.send_error_json("Forbidden", 403)
                return

            # Check version exists and not deleted
            version_info = next((v for v in unit.get("versions", []) if v["n"] == version), None)
            if not version_info or version_info.get("deleted"):
                self.send_error_json("Version not found or deleted", 404)
                return

            # Save current snapshot
            current = unit["current"]
            v_dir = self.units_dir() / uid / "v"
            v_dir.mkdir(exist_ok=True)
            v_file = v_dir / f"{current}.json"
            if not v_file.exists():
                atomic_write(v_file, unit["design"])

            # Load target version
            target_file = v_dir / f"{version}.json"
            if not target_file.exists():
                self.send_error_json("Version snapshot not found", 404)
                return

            design = load_json(target_file)
            unit["design"] = design
            unit["current"] = version
            unit["session"] = {"n": version, "sections": [], "last": 0}
            unit["updated"] = int(time.time())

            unit_file = self.units_dir() / uid / "unit.json"
            atomic_write(unit_file, unit)

        self.send_json(unit)

    def handle_delete_unit_version(self, uid: str):
        """POST /designer/api/units/<uid>/delete-version"""
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
            unit = self.load_unit(uid)
            if not unit:
                self.send_error_json("Unit not found", 404)
                return

            if unit.get("owner") != username:
                self.send_error_json("Forbidden", 403)
                return

            # Check constraints
            if version == unit["current"]:
                self.send_error_json("Cannot delete current version")
                return

            live_version = unit.get("build", {}).get("liveVersion")
            if version == live_version:
                self.send_error_json("Cannot delete live version")
                return

            # Check it's not the only non-deleted version
            non_deleted = [v for v in unit.get("versions", []) if not v.get("deleted")]
            if len(non_deleted) <= 1:
                self.send_error_json("Cannot delete the only version")
                return

            # Mark deleted
            for v in unit["versions"]:
                if v["n"] == version:
                    v["deleted"] = True
                    v["sections"] = ["DELETED"]
                    break

            # Remove snapshot file
            v_file = self.units_dir() / uid / "v" / f"{version}.json"
            if v_file.exists():
                v_file.unlink()

            unit["updated"] = int(time.time())
            unit_file = self.units_dir() / uid / "unit.json"
            atomic_write(unit_file, unit)

        self.send_json(unit)

    # ── Map Management ───────────────────────────────────────────────────────────

    def map_summary(self, map_obj: Dict) -> Dict:
        return {
            "id": map_obj["id"],
            "name": map_obj["name"],
            "created": map_obj["created"],
            "updated": map_obj["updated"],
            "current": map_obj["current"],
            "buildStatus": map_obj.get("build", {}).get("status", "none")
        }

    def handle_list_maps(self):
        """GET /designer/api/maps"""
        username = self.verify_session()
        if not username:
            self.send_error_json("Unauthorized", 401)
            return
        maps = [self.map_summary(m) for _, m in self.iter_maps() if m.get("owner") == username]
        maps.sort(key=lambda m: m["updated"], reverse=True)
        self.send_json({"maps": maps})

    def handle_create_map(self):
        """POST /designer/api/maps {name}"""
        username = self.verify_session()
        if not username:
            self.send_error_json("Unauthorized", 401)
            return
        body = self.read_json_body()
        if body is None:
            return
        name = str(body.get('name', '')).strip()
        if not name or len(name) > 60:
            self.send_error_json("Map name must be 1-60 characters")
            return

        # Check user's map count
        maps_dir = self.maps_dir()
        maps_dir.mkdir(parents=True, exist_ok=True)
        user_maps = sum(1 for _, m in self.iter_maps() if m.get("owner") == username)
        if user_maps >= 20:
            self.send_error_json("Maximum 20 maps per user")
            return

        now = int(time.time())
        design = self.new_map_design()

        with WRITE_LOCK:
            mid = self.new_id()
            while (self.maps_dir() / mid).exists() or not re.fullmatch(r'[A-Za-z0-9_-]+', mid):
                mid = self.new_id()
            map_obj = {
                "id": mid,
                "owner": username,
                "name": name,
                "created": now,
                "updated": now,
                "current": 1,
                "maxVersion": 1,
                "versions": [{"n": 1, "from": None, "sections": [], "created": now, "deleted": False}],
                "session": {"n": 1, "sections": [], "last": now},
                "build": {"status": "none", "liveVersion": None, "requestedAt": None, "builtAt": None},
                "adminNotes": "",
                "bugHistory": [],
                "design": design
            }
            map_dir = self.maps_dir() / mid
            map_dir.mkdir(parents=True, exist_ok=True)
            (map_dir / "v").mkdir(exist_ok=True)
            atomic_write(map_dir / "map.json", map_obj)
            atomic_write(map_dir / "v" / "1.json", design)
        self.send_json(map_obj)

    def handle_get_map(self, mid: str):
        """GET /designer/api/maps/<mid>"""
        username = self.verify_session()
        if not username:
            self.send_error_json("Unauthorized", 401)
            return
        map_obj = self.load_map(mid)
        if not map_obj:
            self.send_error_json("Map not found", 404)
            return
        if map_obj.get("owner") != username:
            self.send_error_json("Forbidden", 403)
            return
        # Add buildAttempted flag
        map_obj["buildAttempted"] = self.has_build_attempt(map_obj, mid, "map")
        # Include claudeQA if it exists
        if "claudeQA" not in map_obj:
            map_obj["claudeQA"] = {}
        # Ensure bugHistory exists
        if "bugHistory" not in map_obj:
            map_obj["bugHistory"] = []
        self.send_json(map_obj)

    def handle_copy_map(self, mid: str):
        """POST /designer/api/maps/<mid>/copy - Create a duplicate of this map"""
        username = self.verify_session()
        if not username:
            self.send_error_json("Unauthorized", 401)
            return

        with WRITE_LOCK:
            map_obj = self.load_map(mid)
            if not map_obj:
                self.send_error_json("Map not found", 404)
                return

            if map_obj.get("owner") != username:
                self.send_error_json("Forbidden", 403)
                return

            # Generate new ID
            new_mid = self.new_id()
            while (self.maps_dir() / new_mid).exists():
                new_mid = self.new_id()

            # Get the map name
            map_name = map_obj.get("name", "Unnamed Map")
            now = int(time.time())

            # Create deep copy of design
            new_design = json.loads(json.dumps(map_obj["design"]))

            new_map = {
                "id": new_mid,
                "owner": username,
                "name": f"Copy of {map_name}",
                "created": now,
                "updated": now,
                "adminNotes": "",
                "bugHistory": [],
                "design": new_design,
                "build": {"status": "none", "liveVersion": None, "requestedAt": None, "builtAt": None},
                "current": 1,
                "maxVersion": 1,
                "versions": [{"n": 1, "from": None, "sections": [], "created": now, "deleted": False}],
                "session": {"n": 1, "sections": [], "last": now}
            }

            # Create map directory and save
            (self.maps_dir() / new_mid).mkdir(parents=True, exist_ok=True)
            v_dir = self.maps_dir() / new_mid / "v"
            v_dir.mkdir(exist_ok=True)
            atomic_write(self.maps_dir() / new_mid / "map.json", new_map)
            atomic_write(v_dir / "1.json", new_design)

        self.send_json(new_map)

    def handle_rename_map(self, mid: str):
        """POST /designer/api/maps/<mid>/rename {name} - Update map name"""
        username = self.verify_session()
        if not username:
            self.send_error_json("Unauthorized", 401)
            return

        body = self.read_json_body()
        if not body:
            return

        new_name = body.get('name', '').strip()

        if not new_name:
            self.send_error_json("Map name is required")
            return

        with WRITE_LOCK:
            map_obj = self.load_map(mid)
            if not map_obj:
                self.send_error_json("Map not found", 404)
                return

            if map_obj.get("owner") != username:
                self.send_error_json("Forbidden", 403)
                return

            map_obj["name"] = new_name
            map_obj["updated"] = int(time.time())
            atomic_write(self.maps_dir() / mid / "map.json", map_obj)

        self.send_json({"ok": True, "name": new_name})

    def handle_patch_map(self, mid: str):
        """POST /designer/api/maps/<mid>/patch"""
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
            map_obj = self.load_map(mid)
            if not map_obj:
                self.send_error_json("Map not found", 404)
                return

            if map_obj["owner"] != username:
                self.send_error_json("Forbidden", 403)
                return

            # Apply ops (similar to faction patch)
            for op in ops:
                if not self.apply_map_patch_op(map_obj, op, mid):
                    return  # Error already sent

            # Save map
            map_obj["updated"] = int(time.time())
            map_file = self.maps_dir() / mid / "map.json"
            atomic_write(map_file, map_obj)

            # Always rewrite current version snapshot
            v_file = self.maps_dir() / mid / "v" / f"{map_obj['current']}.json"
            atomic_write(v_file, map_obj["design"])

        self.send_json({
            "current": map_obj["current"],
            "maxVersion": map_obj["maxVersion"],
            "versions": map_obj["versions"],
            "session": map_obj["session"],
            "updated": map_obj["updated"]
        })

    def apply_map_patch_op(self, map_obj: Dict, op: Dict, mid: str) -> bool:
        """Apply a single patch operation to a map. Return False on error."""
        op_type = op.get('op')
        path = op.get('path', '')

        # Extract section key (first path segment)
        parts = path.split('.')
        if not parts:
            self.send_error_json("Invalid path")
            return False

        section = parts[0]
        valid_sections = ['images', 'bitmaps', 'adjacency', 'units', 'tokens', 'sb', 'glyphs', 'abilities']
        if section not in valid_sections:
            self.send_error_json(f"Unknown section: {section}")
            return False

        # Determine if this is an addition or change
        is_addition = self.is_map_addition(map_obj, op)

        # Check if version is locked
        current = map_obj["current"]
        max_version = map_obj["maxVersion"]
        live_version = map_obj.get("build", {}).get("liveVersion")
        is_locked = current < max_version or current == live_version

        # Check open session
        now = time.time()
        session = map_obj["session"]
        is_open_session = (
            session["n"] == current and
            now - session["last"] < 600 and
            section in session["sections"]
        )

        # Decide: new version or in-place
        if is_locked:
            self.create_new_map_version(map_obj, section, mid)
        elif is_addition:
            pass  # Apply in place, add section to version
        elif not is_open_session:
            self.create_new_map_version(map_obj, section, mid)

        # Apply the operation
        if not self.apply_op_to_design(map_obj["design"], op):
            return False

        # Update session
        session["last"] = int(now)
        if session["n"] == map_obj["current"]:
            if section not in session["sections"]:
                session["sections"].append(section)
        else:
            session["n"] = map_obj["current"]
            session["sections"] = [section]

        # Add section to current version's sections if not present
        for v in map_obj["versions"]:
            if v["n"] == map_obj["current"]:
                if section not in v["sections"]:
                    v["sections"].append(section)
                break

        return True

    def is_map_addition(self, map_obj: Dict, op: Dict) -> bool:
        """Check if operation is an addition (empty→non-empty) for a map."""
        op_type = op.get('op')
        path = op.get('path', '')
        design = map_obj["design"]

        if op_type == 'addRow':
            row = op.get('row', {})
            return self.is_blank_map_row(row, path)

        if op_type == 'deleteRow':
            table_path = op.get('path', '')
            row_id = op.get('id')
            row = self.find_row(design, table_path, row_id)
            if row:
                return self.is_blank_map_row(row, table_path)
            return True

        if op_type == 'set':
            value = op.get('value')
            current = self.get_path_value(design, path)
            current_empty = current in ("", None, [])
            value_empty = value in ("", None, [])
            return current_empty and not value_empty

        return False

    def is_blank_map_row(self, row: Dict, table_path: str) -> bool:
        """Check if a map row is completely blank."""
        for k, v in row.items():
            if k == 'id':
                continue
            if v not in ("", None, [], False, 0):
                return False
        return True

    def create_new_map_version(self, map_obj: Dict, section: str, mid: str):
        """Create a new version and freeze the current one for a map."""
        current = map_obj["current"]
        max_version = map_obj["maxVersion"]

        # Freeze current version
        v_file = self.maps_dir() / mid / "v" / f"{current}.json"
        if not v_file.exists():
            atomic_write(v_file, map_obj["design"])

        # Create new version
        new_n = max_version + 1
        now = int(time.time())

        map_obj["versions"].append({
            "n": new_n,
            "from": current,
            "sections": [section],
            "created": now,
            "deleted": False
        })

        map_obj["current"] = new_n
        map_obj["maxVersion"] = new_n
        map_obj["session"] = {"n": new_n, "sections": [section], "last": now}

    def handle_close_map_session(self, mid: str):
        """POST /designer/api/maps/<mid>/close-session"""
        username = self.verify_session()
        if not username:
            self.send_error_json("Unauthorized", 401)
            return

        with WRITE_LOCK:
            map_obj = self.load_map(mid)
            if not map_obj:
                self.send_error_json("Map not found", 404)
                return

            if map_obj["owner"] != username:
                self.send_error_json("Forbidden", 403)
                return

            # Clear session by resetting last time to far past
            map_obj["session"]["last"] = 0

            map_file = self.maps_dir() / mid / "map.json"
            atomic_write(map_file, map_obj)

        self.send_json({})

    def handle_rollback_map(self, mid: str):
        """POST /designer/api/maps/<mid>/rollback"""
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
            map_obj = self.load_map(mid)
            if not map_obj:
                self.send_error_json("Map not found", 404)
                return

            if map_obj["owner"] != username:
                self.send_error_json("Forbidden", 403)
                return

            # Check version exists and not deleted
            version_info = next((v for v in map_obj["versions"] if v["n"] == version), None)
            if not version_info or version_info.get("deleted"):
                self.send_error_json("Version not found or deleted", 404)
                return

            # Save current snapshot
            current = map_obj["current"]
            v_file = self.maps_dir() / mid / "v" / f"{current}.json"
            if not v_file.exists():
                atomic_write(v_file, map_obj["design"])

            # Load target version
            target_file = self.maps_dir() / mid / "v" / f"{version}.json"
            if not target_file.exists():
                self.send_error_json("Version snapshot not found", 404)
                return

            design = load_json(target_file)
            map_obj["design"] = design
            map_obj["current"] = version
            map_obj["session"] = {"n": version, "sections": [], "last": 0}
            map_obj["updated"] = int(time.time())

            map_file = self.maps_dir() / mid / "map.json"
            atomic_write(map_file, map_obj)

        self.send_json(map_obj)

    def handle_delete_map_version(self, mid: str):
        """POST /designer/api/maps/<mid>/delete-version"""
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
            map_obj = self.load_map(mid)
            if not map_obj:
                self.send_error_json("Map not found", 404)
                return

            if map_obj["owner"] != username:
                self.send_error_json("Forbidden", 403)
                return

            # Check constraints
            if version == map_obj["current"]:
                self.send_error_json("Cannot delete current version")
                return

            live_version = map_obj.get("build", {}).get("liveVersion")
            if version == live_version:
                self.send_error_json("Cannot delete live version")
                return

            # Check it's not the only non-deleted version
            non_deleted = [v for v in map_obj["versions"] if not v.get("deleted")]
            if len(non_deleted) <= 1:
                self.send_error_json("Cannot delete the only version")
                return

            # Mark deleted
            for v in map_obj["versions"]:
                if v["n"] == version:
                    v["deleted"] = True
                    v["sections"] = ["DELETED"]
                    break

            # Remove snapshot file
            v_file = self.maps_dir() / mid / "v" / f"{version}.json"
            if v_file.exists():
                v_file.unlink()

            map_obj["updated"] = int(time.time())
            map_file = self.maps_dir() / mid / "map.json"
            atomic_write(map_file, map_obj)

        self.send_json(map_obj)

    def handle_create_map_request(self, mid: str):
        """POST /designer/api/maps/<mid>/request"""
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

        valid_types = ['build', 'extract', 'bug']
        if req_type not in valid_types:
            self.send_error_json(f"Invalid request type. Must be one of: {', '.join(valid_types)}")
            return

        map_obj = self.load_map(mid)
        if not map_obj:
            self.send_error_json("Map not found", 404)
            return

        if map_obj["owner"] != username:
            self.send_error_json("Forbidden", 403)
            return

        # Load requests
        requests_file = self.server.data_dir / "requests.json"
        requests_data = load_json(requests_file) or {"requests": []}
        requests = requests_data.get("requests", [])

        # Check for duplicate
        for existing in requests:
            if (existing.get("type") == req_type and
                existing.get("mid") == mid and
                existing.get("status") in ("open", "notified") and
                existing.get("data") == data):
                self.send_json(existing)
                return

        # Create new request
        now = int(time.time())
        req_id = f"r_{secrets.token_urlsafe(6)}"

        request = {
            "id": req_id,
            "type": req_type,
            "kind": "map",
            "mid": mid,
            "mapName": map_obj["name"],
            "user": username,
            "status": "open",
            "created": now,
            "updated": now,
            "text": text,
            "data": data,
            "designObjectName": map_obj["name"]
        }

        with WRITE_LOCK:
            requests.append(request)
            requests_data["requests"] = requests
            atomic_write(requests_file, requests_data)
            # Every designer prompt also goes into the admin console's Claude terminal log
            self.add_terminal_entry(self.terminal_type(request), self.display_name(username),
                                    text or f"{req_type} request for map {map_obj['name']}",
                                    "Waiting to be picked up.", ref=req_id, designObject=map_obj['name'])

            # Write to console queue for build requests
            if req_type == "build":
                queue_written = False
                try:
                    clean_name = map_obj["name"].replace('\n', ' ').replace('[', '').replace(']', '')
                    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
                    display_user = self.display_name(username)
                    queue_line = f"[{timestamp}] MAP-BUILD {req_id}: Build the map \"{clean_name}\" designed by {display_user} into the homebrew build (designer map id {mid}).\n"
                    with open(self.server.console_queue_path, 'a') as f:
                        f.write(queue_line)
                    queue_written = True
                except OSError:
                    pass

                if queue_written:
                    request["status"] = "notified"
                    atomic_write(requests_file, requests_data)

                # Update build status
                map_obj["build"] = map_obj.get("build", {
                    "status": "none",
                    "liveVersion": None,
                    "requestedAt": None,
                    "builtAt": None
                })
                map_obj["build"]["status"] = "requested"
                map_obj["build"]["requestedAt"] = now
                atomic_write(self.maps_dir() / mid / "map.json", map_obj)
            elif req_type == "extract":
                queue_written = False
                try:
                    clean_name = map_obj["name"].replace('\n', ' ').replace('[', '').replace(']', '')
                    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
                    display_user = self.display_name(username)
                    queue_line = f"[{timestamp}] MAP-EXTRACT {req_id}: Extract map design details for \"{clean_name}\" designed by {display_user} (designer map id {mid}).\n"
                    with open(self.server.console_queue_path, 'a') as f:
                        f.write(queue_line)
                    queue_written = True
                except OSError:
                    pass

                if queue_written:
                    request["status"] = "notified"
                    atomic_write(requests_file, requests_data)
            elif req_type == "bug":
                queue_written = False
                try:
                    clean_name = map_obj["name"].replace('\n', ' ').replace('[', '').replace(']', '')
                    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
                    display_user = self.display_name(username)
                    queue_line = f"[{timestamp}] MAP-BUG {req_id}: Bug report for map \"{clean_name}\" from {display_user} (designer map id {mid}).\n"
                    with open(self.server.console_queue_path, 'a') as f:
                        f.write(queue_line)
                    queue_written = True
                except OSError:
                    pass

                if queue_written:
                    request["status"] = "notified"
                    atomic_write(requests_file, requests_data)

                # Add bug to bugHistory
                if "bugHistory" not in map_obj:
                    map_obj["bugHistory"] = []
                bug_entry = {
                    "bugNumber": req_id,
                    "submittedAt": now,
                    "description": data.get("description", ""),
                    "response": None,
                    "respondedAt": None
                }
                map_obj["bugHistory"].append(bug_entry)
                atomic_write(self.maps_dir() / mid / "map.json", map_obj)

        self.send_json(request)

    def handle_get_map_requests(self, mid: str):
        """GET /designer/api/maps/<mid>/requests"""
        username = self.verify_session()
        if not username:
            self.send_error_json("Unauthorized", 401)
            return

        map_obj = self.load_map(mid)
        if not map_obj:
            self.send_error_json("Map not found", 404)
            return

        if map_obj["owner"] != username:
            self.send_error_json("Forbidden", 403)
            return

        requests_file = self.server.data_dir / "requests.json"
        requests_data = load_json(requests_file) or {"requests": []}
        requests = requests_data.get("requests", [])

        map_requests = [r for r in requests if r.get("mid") == mid]
        map_requests.sort(key=lambda r: r.get("created", 0), reverse=True)

        self.send_json({"requests": map_requests})

    def handle_get_map_extract_queue(self, mid: str):
        """GET /designer/api/maps/<mid>/extract-queue"""
        username = self.verify_session()
        if not username:
            self.send_error_json("Unauthorized", 401)
            return
        map_obj = self.load_map(mid)
        if not map_obj:
            self.send_error_json("Map not found", 404)
            return
        if map_obj["owner"] != username:
            self.send_error_json("Forbidden", 403)
            return
        # Reuse extract_queue_position logic but for maps
        self.send_json({"status": self.extract_queue_position_for_map(mid)})

    def extract_queue_position_for_map(self, mid: str) -> Optional[Dict]:
        """Extraction status for maps."""
        requests = (load_json(self.server.data_dir / "requests.json") or {}).get("requests", [])
        queue = sorted((r for r in requests if r.get("type") == "extract" and r.get("status") == "open" and r.get("kind") == "map"),
                       key=lambda r: r.get("created", 0))
        mine = next((r for r in queue if r.get("mid") == mid), None)
        if not mine:
            return None
        if mine.get("startedAt"):
            return {"state": "in_process"}
        if not mine.get("pickedUp"):
            return {"state": "waiting"}
        waiting = [r for r in queue if not r.get("startedAt")]
        return {"state": "queued", "position": waiting.index(mine) + 1}

    def handle_submit_map_answers(self, mid: str):
        """POST /designer/api/maps/<mid>/answers {section, text}"""
        username = self.verify_session()
        if not username:
            self.send_error_json("Unauthorized", 401)
            return

        body = self.read_json_body()
        if not body:
            return

        section = body.get('section', '').strip()
        text = body.get('text', '').strip()

        if not section:
            self.send_error_json("section is required")
            return

        map_obj = self.load_map(mid)
        if not map_obj:
            self.send_error_json("Map not found", 404)
            return
        if map_obj.get("owner") != username:
            self.send_error_json("Forbidden", 403)
            return

        # Find section label
        section_titles = [
            {'key': 'regions', 'title': 'Regions'},
            {'key': 'tokens', 'title': 'Tokens'},
            {'key': 'custom', 'title': 'Custom Elements'},
            {'key': 'rules', 'title': 'Rules'}
        ]
        section_label = next((s['title'] for s in section_titles if s['key'] == section), section)

        now = int(time.time())

        with WRITE_LOCK:
            # Save answers
            if "claudeQA" not in map_obj:
                map_obj["claudeQA"] = {}
            if section not in map_obj["claudeQA"]:
                map_obj["claudeQA"][section] = {"questions": "", "answers": "", "updated": 0}
            map_obj["claudeQA"][section]["answers"] = text
            map_obj["claudeQA"][section]["updated"] = now
            map_obj["updated"] = now
            build = map_obj.get("build") or {}
            if build.get("status") == "needs_answers":
                build["status"] = "requested"
            atomic_write(self.maps_dir() / mid / "map.json", map_obj)

            # Create request
            requests_file = self.server.data_dir / "requests.json"
            requests_data = load_json(requests_file) or {"requests": []}
            requests = requests_data.get("requests", [])

            # Check for duplicate
            for existing in requests:
                if (existing.get("type") == "answers" and
                    existing.get("mid") == mid and
                    existing.get("status") == "open" and
                    existing.get("data", {}).get("section") == section and
                    existing.get("text") == text):
                    self.send_json(existing)
                    return

            req_id = f"r_{secrets.token_urlsafe(6)}"
            request = {
                "id": req_id,
                "type": "answers",
                "kind": "map",
                "mid": mid,
                "mapName": map_obj["name"],
                "user": username,
                "status": "open",
                "created": now,
                "updated": now,
                "text": text,
                "data": {"section": section}
            }
            requests.append(request)
            requests_data["requests"] = requests
            atomic_write(requests_file, requests_data)

            # Write queue line to console queue file
            queue_written = False
            try:
                clean_name = map_obj["name"].replace('\n', ' ').replace('[', '').replace(']', '')
                timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
                display_user = self.display_name(username)
                queue_line = f"[{timestamp}] DESIGN-ANSWERS {req_id}: {display_user} answered Claude's questions on the \"{section_label}\" section of map {clean_name} (designer map id {mid}, section {section}). Read the questions and answers with tickers/designer-admin.py qa {mid} {section}.\n"
                with open(self.server.console_queue_path, 'a') as f:
                    f.write(queue_line)
                queue_written = True
            except OSError:
                pass

            if queue_written:
                request["status"] = "notified"
                requests_data["requests"] = requests
                atomic_write(requests_file, requests_data)

        self.send_json(request)

    def sync_build_status(self, request: Dict, status: str):
        """Keep a design's build status in step with its build / answers request (caller holds
        WRITE_LOCK): picked up -> in progress; finished but not built -> waiting for the
        designer's answers if Claude left questions, otherwise back to not submitted."""
        if request.get("type") not in ("build", "answers") or status not in ("in_progress", "done", "cancelled"):
            return
        if request.get("uid"):
            entity, f = self.load_unit(request["uid"]), self.units_dir() / request["uid"] / "unit.json"
        elif request.get("fid"):
            entity = self.load_faction(request["fid"])
            f = self.server.data_dir / "factions" / request["fid"] / "faction.json"
        elif request.get("mid"):
            entity = self.load_map(request["mid"])
            f = self.maps_dir() / request["mid"] / "map.json"
        else:
            return
        if not entity:
            return
        build = entity.setdefault("build", {"status": "none", "liveVersion": None, "requestedAt": None, "builtAt": None})
        if build.get("status") == "built":
            return
        if status == "in_progress":
            new = "in_progress"
        elif any(sec.get("questions") for sec in entity.get("claudeQA", {}).values()):
            new = "needs_answers"
        else:
            new = "none"
        if build.get("status") != new:
            build["status"] = new
            entity["updated"] = int(time.time())
            atomic_write(f, entity)

    def update_bug_history_response(self, request: Dict, response_text: str):
        """Update bugHistory with response when bug request is marked done (caller holds WRITE_LOCK)."""
        bug_id = request.get("id")
        if not bug_id:
            return
        now = int(time.time())
        if request.get("fid"):
            entity = self.load_faction(request["fid"])
            f = self.server.data_dir / "factions" / request["fid"] / "faction.json"
        elif request.get("uid"):
            entity = self.load_unit(request["uid"])
            f = self.units_dir() / request["uid"] / "unit.json"
        elif request.get("mid"):
            entity = self.load_map(request["mid"])
            f = self.maps_dir() / request["mid"] / "map.json"
        else:
            return
        if not entity:
            return
        bugHistory = entity.get("bugHistory", [])
        for entry in bugHistory:
            if entry.get("bugNumber") == bug_id:
                entry["response"] = response_text
                entry["respondedAt"] = now
                entity["updated"] = int(time.time())
                atomic_write(f, entity)
                return

    def has_build_attempt(self, entity: Dict, entity_id: str, entity_type: str) -> bool:
        """Check if a faction, unit, or map has had a build attempted."""
        build = entity.get("build", {})
        # Check if build status is not "none"
        if build.get("status", "none") != "none":
            return True
        # Check if requestedAt is set
        if build.get("requestedAt"):
            return True
        # Check if any claudeQA section has non-empty questions
        claudeQA = entity.get("claudeQA", {})
        if any(sec.get("questions") for sec in claudeQA.values()):
            return True
        # Check requests.json for build requests
        requests_file = self.server.data_dir / "requests.json"
        requests_data = load_json(requests_file) or {"requests": []}
        requests = requests_data.get("requests", [])
        if entity_type == "faction":
            key = "fid"
        elif entity_type == "unit":
            key = "uid"
        else:  # map
            key = "mid"
        if any(r.get(key) == entity_id and r.get("type") in ("build", "update") for r in requests):
            return True
        return False

    def is_base_faction(self, faction: Dict) -> bool:
        """Check if a faction is a base faction (read-only for non-admin users)."""
        return faction.get("base") or faction.get("owner") == "base"

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

        # Base factions are visible to everyone read-only, except cavysupreme can edit them
        is_base = self.is_base_faction(faction)
        if is_base:
            read_only = username != "cavysupreme"
        else:
            is_owner = faction["owner"] == username
            is_editor = username in faction.get("editors", [])
            is_viewer = username in faction.get("viewers", [])

            read_only = not (is_owner or is_editor)

            if not (is_owner or is_editor or is_viewer):
                self.send_error_json("Forbidden", 403)
                return

        response = dict(faction)
        if read_only:
            response["readOnly"] = True
            response["ownerName"] = self.display_name(faction["owner"])
        response["builtDesign"] = self.built_design_with_overrides(fid, faction)
        response["liveValues"] = self.load_live_values(fid)
        response["extractQueue"] = self.extract_queue_position(fid)
        response["buildAttempted"] = self.has_build_attempt(faction, fid, "faction")
        # Include claudeQA if it exists
        if "claudeQA" not in response:
            response["claudeQA"] = {}
        # Ensure bugHistory exists
        if "bugHistory" not in response:
            response["bugHistory"] = []
        # Add spellbook guidance to design for Claude
        if "design" in response:
            response["design"]["spellbookGuidance"] = compute_spellbook_guidance(response["design"])
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
        if faction["owner"] != username and username not in faction.get("editors", []) and username not in faction.get("viewers", []):
            self.send_error_json("Forbidden", 403)
            return
        self.send_json({"status": self.extract_queue_position(fid)})

    def handle_public_stability(self):
        """GET /designer/api/public/stability - Public endpoint, no auth required"""
        result = {}
        factions_dir = self.server.data_dir / "factions"
        if not factions_dir.exists():
            self.send_json(result)
            return

        # Scan all factions and collect stability for designer factions with a stability set
        for faction_dir in factions_dir.iterdir():
            if not faction_dir.is_dir():
                continue
            faction_file = faction_dir / "faction.json"
            if not faction_file.exists():
                continue
            faction = load_json(faction_file)
            if not faction:
                continue

            # Only include factions with a stability field set
            stability = faction.get("stability")
            acronym = faction.get("acronym")
            if stability and acronym:
                result[acronym] = stability

        self.send_json(result)

    def handle_set_stability(self, fid: str):
        """POST /designer/api/factions/<fid>/stability"""
        username = self.verify_session()
        if not username:
            self.send_error_json("Unauthorized", 401)
            return

        body = self.read_json_body()
        if not body:
            return

        stability = body.get('stability')
        valid_values = ['alpha', 'beta', 'stable']
        if stability not in valid_values:
            self.send_error_json(f"Invalid stability. Must be one of: {', '.join(valid_values)}")
            return

        with WRITE_LOCK:
            faction = self.load_faction(fid)
            if not faction:
                self.send_error_json("Faction not found", 404)
                return

            # Check if owner or if base faction (only admin can modify those via admin endpoint)
            is_owner = faction["owner"] == username
            base_faction = faction.get("base", False)

            if base_faction:
                self.send_error_json("Only admin can modify base factions", 403)
                return

            if not is_owner:
                self.send_error_json("Forbidden", 403)
                return

            faction["stability"] = stability
            faction["updated"] = int(time.time())

            faction_file = self.server.data_dir / "factions" / fid / "faction.json"
            atomic_write(faction_file, faction)

        self.send_json({"ok": True, "stability": stability})

    def handle_copy_faction(self, fid: str):
        """POST /designer/api/factions/<fid>/copy - Create a duplicate of this faction"""
        username = self.verify_session()
        if not username:
            self.send_error_json("Unauthorized", 401)
            return

        with WRITE_LOCK:
            faction = self.load_faction(fid)
            if not faction:
                self.send_error_json("Faction not found", 404)
                return

            # Check if owner or if base faction (base cannot be copied)
            if faction["owner"] != username and username not in faction.get("editors", []):
                self.send_error_json("Forbidden", 403)
                return

            if faction.get("base", False):
                self.send_error_json("Cannot copy base factions", 403)
                return

            # Generate new ID
            new_fid = secrets.token_urlsafe(9).replace('_', '').replace('-', '').lower()[:12]
            while (self.server.data_dir / "factions" / new_fid).exists():
                new_fid = secrets.token_urlsafe(9).replace('_', '').replace('-', '').lower()[:12]

            # Create new faction with "Copy of" prefix
            now = int(time.time())
            new_faction = {
                "id": new_fid,
                "owner": username,
                "name": f"Copy of {faction['name']}",
                "acronym": self.generate_unique_acronym(faction.get('acronym', 'COP')),
                "created": now,
                "updated": now,
                "current": 1,
                "maxVersion": 1,
                "versions": [{"n": 1, "from": None, "sections": [], "created": now, "deleted": False}],
                "session": {"n": 1, "sections": [], "last": now},
                "build": {"status": "none", "liveVersion": None, "requestedAt": None, "builtAt": None, "history": []},
                "liveGameVersions": [],
                "adminNotes": "",
                "bugHistory": [],
                "design": json.loads(json.dumps(faction["design"]))  # Deep copy
            }

            # Create faction directory
            faction_dir = self.server.data_dir / "factions" / new_fid
            faction_dir.mkdir(exist_ok=True)
            (faction_dir / "v").mkdir(exist_ok=True)

            # Save faction and initial version
            atomic_write(faction_dir / "faction.json", new_faction)
            atomic_write(faction_dir / "v" / "1.json", new_faction["design"])

        self.send_json(new_faction)

    def generate_unique_acronym(self, base_acronym: str) -> str:
        """Generate a unique acronym based on the given base, appending numbers if needed."""
        reserved = self.server.reserved_acronyms
        acronym = base_acronym.upper()[:3]

        # Ensure it's 2-3 chars
        if len(acronym) < 2:
            acronym = (acronym + 'X')[:3]

        # Check if reserved or in use
        if acronym not in reserved and not self.acronym_exists(acronym):
            return acronym

        # Try prefix + number, truncating the PREFIX (not the number) so the
        # candidate always changes. The old (original + str(n))[:3] form cut the
        # digit off any 3-letter acronym and looped forever while holding
        # WRITE_LOCK (pegged the VM's CPU on 2026-10-14).
        original = acronym
        for counter in range(1, 100):
            suffix = str(counter)
            candidate = original[:3 - len(suffix)] + suffix
            if candidate not in reserved and not self.acronym_exists(candidate):
                return candidate

        # Fallback: random 3-char acronym (bounded, never loops forever)
        for _ in range(1000):
            candidate = original[:1] + secrets.token_hex(1).upper()
            if candidate not in reserved and not self.acronym_exists(candidate):
                return candidate
        return original

    def acronym_exists(self, acronym: str) -> bool:
        """Check if an acronym is already in use."""
        factions_dir = self.server.data_dir / "factions"
        if not factions_dir.exists():
            return False
        for fid_dir in factions_dir.iterdir():
            if not fid_dir.is_dir():
                continue
            faction_file = fid_dir / "faction.json"
            if faction_file.exists():
                existing = load_json(faction_file)
                if existing.get("acronym") == acronym:
                    return True
        return False

    def handle_rename_faction(self, fid: str):
        """POST /designer/api/factions/<fid>/rename {name, acronym} - Update faction name and/or acronym"""
        username = self.verify_session()
        if not username:
            self.send_error_json("Unauthorized", 401)
            return

        body = self.read_json_body()
        if not body:
            return

        new_name = body.get('name', '').strip()
        new_acronym = body.get('acronym', '').strip().upper()

        errors = []
        if new_name and len(new_name) < 5:
            errors.append("Name must be at least 5 characters")
        if new_acronym and not re.match(r'^[A-Z0-9]{2,3}$', new_acronym):
            errors.append("Acronym must be 2-3 letters or digits")

        if errors:
            self.send_error_json("; ".join(errors))
            return

        with WRITE_LOCK:
            faction = self.load_faction(fid)
            if not faction:
                self.send_error_json("Faction not found", 404)
                return

            if faction["owner"] != username and username not in faction.get("editors", []):
                self.send_error_json("Forbidden", 403)
                return

            # Check if new acronym is reserved or in use by another faction
            if new_acronym:
                reserved = self.server.reserved_acronyms
                if new_acronym in reserved:
                    self.send_error_json(f"Acronym {new_acronym} is reserved")
                    return

                # Check other factions
                factions_dir = self.server.data_dir / "factions"
                for other_fid_dir in factions_dir.iterdir():
                    if not other_fid_dir.is_dir() or other_fid_dir.name == fid:
                        continue
                    other_file = other_fid_dir / "faction.json"
                    if other_file.exists():
                        other = load_json(other_file)
                        if other.get("acronym") == new_acronym:
                            self.send_error_json(f"Acronym {new_acronym} is already in use")
                            return

            # Update faction
            if new_name:
                faction["name"] = new_name
            if new_acronym:
                faction["acronym"] = new_acronym

            faction["updated"] = int(time.time())
            faction_file = self.server.data_dir / "factions" / fid / "faction.json"
            atomic_write(faction_file, faction)

        self.send_json({"ok": True, "name": faction.get("name"), "acronym": faction.get("acronym")})

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

            # Base factions are read-only for non-admin users (except cavysupreme)
            if self.is_base_faction(faction):
                if username != "cavysupreme":
                    self.send_error_json("Base factions are read-only", 403)
                    return
            elif faction["owner"] != username and username not in faction.get("editors", []):
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

    def backfill_section(self, design: Dict, section: str, defaults: Optional[Dict] = None):
        """Older designs were saved before some sections existed (e.g. 'interactions').
        Fill the missing section with its default; interactions rows use the same fixed ids
        as Rules.backfillDesign in www/rules.js so the page's edits land on the right rows."""
        if section in design:
            return
        defaults = defaults if defaults is not None else self.new_design()
        if section in defaults:
            sec = defaults[section]
            if section == 'interactions':
                for row, rid in zip(sec["rows"], ('ia-sleeper', 'ia-neutral', 'ia-bubastis')):
                    row["id"] = rid
            design[section] = sec

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
        valid_sections = ['ae', 'ufa', 'setup', 'units', 'sbr', 'sb', 'region', 'tokens', 'custom', 'menus', 'interactions', 'card', 'sbImages', 'sbImagesB', 'meta']
        if section not in valid_sections:
            self.send_error_json(f"Unknown section: {section}")
            return False

        # Older designs were saved before some sections existed (e.g. 'interactions').
        # Fill the missing section with its default; interactions rows use the same fixed ids
        # as Rules.backfillDesign in www/rules.js so the page's edits land on the right rows.
        self.backfill_section(faction["design"], section)

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

            # Base factions are read-only for non-admin users (except cavysupreme)
            if self.is_base_faction(faction):
                if username != "cavysupreme":
                    self.send_error_json("Base factions are read-only", 403)
                    return
            elif faction["owner"] != username and username not in faction.get("editors", []):
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

            # Base factions are read-only for non-admin users (except cavysupreme)
            if self.is_base_faction(faction):
                if username != "cavysupreme":
                    self.send_error_json("Base factions are read-only", 403)
                    return
            elif faction["owner"] != username and username not in faction.get("editors", []):
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

            # Base factions are read-only for non-admin users (except cavysupreme)
            if self.is_base_faction(faction):
                if username != "cavysupreme":
                    self.send_error_json("Base factions are read-only", 403)
                    return
            elif faction["owner"] != username and username not in faction.get("editors", []):
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

        valid_types = ['build', 'update', 'simple_update', 'extract', 'bug', 'answers']
        if req_type not in valid_types:
            self.send_error_json(f"Invalid request type. Must be one of: {', '.join(valid_types)}")
            return

        faction = self.load_faction(fid)
        if not faction:
            self.send_error_json("Faction not found", 404)
            return

        # Base factions are read-only for non-admin users (except cavysupreme)
        if self.is_base_faction(faction):
            if username != "cavysupreme":
                self.send_error_json("Base factions are read-only", 403)
                return
        elif faction["owner"] != username:
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
                existing.get("status") in ("open", "notified") and
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
            "data": data,
            "designObjectName": faction["name"]
        }

        with WRITE_LOCK:
            requests.append(request)
            requests_data["requests"] = requests
            atomic_write(requests_file, requests_data)
            # Every designer prompt also goes into the admin console's Claude terminal log
            self.add_terminal_entry(self.terminal_type(request), self.display_name(username),
                                    text or f"{req_type} request for {faction['name']}",
                                    "Waiting to be picked up.", ref=req_id, designObject=faction['name'], faction=faction['name'])

            # Faction builds go straight to the admin console queue (owner's standing OK to attempt them)
            if req_type == "build":
                try:
                    clean_name = faction["name"].replace('\n', ' ').replace('[', '').replace(']', '')
                    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
                    with open(self.server.console_queue_path, 'a') as qf:
                        qf.write(f"[{timestamp}] FACTION-BUILD {req_id}: Build the faction \"{clean_name}\" "
                                 f"({faction['acronym']}) designed by {self.display_name(username)} into the homebrew "
                                 f"build (designer faction id {fid}).\n")
                    request["status"] = "notified"
                    atomic_write(requests_file, requests_data)
                except OSError:
                    pass

            # Set build.requestedAt for build/update requests to enable buildAttempted flag
            if req_type in ("build", "update"):
                if "build" not in faction:
                    faction["build"] = {"status": "none", "liveVersion": None, "requestedAt": None, "builtAt": None}
                if not faction["build"].get("requestedAt"):
                    faction["build"]["requestedAt"] = now
                # Submitted and waiting to be picked up (an update to a built faction stays Built)
                if req_type == "build" and faction["build"].get("status") != "built":
                    faction["build"]["status"] = "requested"
                faction_file = self.server.data_dir / "factions" / fid / "faction.json"
                atomic_write(faction_file, faction)

            # Add bug to bugHistory
            if req_type == "bug":
                if "bugHistory" not in faction:
                    faction["bugHistory"] = []
                bug_entry = {
                    "bugNumber": req_id,
                    "submittedAt": now,
                    "description": data.get("description", ""),
                    "response": None,
                    "respondedAt": None
                }
                faction["bugHistory"].append(bug_entry)
                faction_file = self.server.data_dir / "factions" / fid / "faction.json"
                atomic_write(faction_file, faction)

                queue_written = False
                try:
                    clean_name = faction["name"].replace('\n', ' ').replace('[', '').replace(']', '')
                    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
                    display_user = self.display_name(username)
                    queue_line = f"[{timestamp}] FACTION-BUG {req_id}: Bug report for faction \"{clean_name}\" ({faction['acronym']}) from {display_user} (designer faction id {fid}).\n"
                    with open(self.server.console_queue_path, 'a') as f:
                        f.write(queue_line)
                    queue_written = True
                except OSError:
                    pass

                if queue_written:
                    request["status"] = "notified"
                    atomic_write(requests_file, requests_data)

        self.send_json(request)

    def handle_submit_answers(self, fid_or_uid: str, entity_type: str):
        """POST /designer/api/factions/<fid>/answers or /designer/api/units/<uid>/answers {section, text}"""
        username = self.verify_session()
        if not username:
            self.send_error_json("Unauthorized", 401)
            return

        body = self.read_json_body()
        if not body:
            return

        section = body.get('section', '').strip()
        text = body.get('text', '').strip()

        if not section:
            self.send_error_json("section is required")
            return

        if entity_type == "faction":
            entity = self.load_faction(fid_or_uid)
            if not entity:
                self.send_error_json("Faction not found", 404)
                return
            if entity["owner"] != username:
                self.send_error_json("Forbidden", 403)
                return
            entity_name = entity["name"]
            entity_file = self.server.data_dir / "factions" / fid_or_uid / "faction.json"
        else:  # unit
            entity = self.load_unit(fid_or_uid)
            if not entity:
                self.send_error_json("Unit not found", 404)
                return
            if entity.get("owner") != username:
                self.send_error_json("Forbidden", 403)
                return
            row = (entity.get("design", {}).get("units", {}).get("rows") or [{}])[0]
            entity_name = row.get("name") or "Unit"
            entity_file = self.units_dir() / fid_or_uid / "unit.json"

        # Find section label
        section_titles = [
            {'key': 'ae', 'title': 'Alternate economy'},
            {'key': 'ufa', 'title': 'Unique faction ability'},
            {'key': 'setup', 'title': 'Setup'},
            {'key': 'units', 'title': 'Units'},
            {'key': 'sbr', 'title': 'Spell Book Requirements'},
            {'key': 'sb', 'title': 'Spellbooks'},
            {'key': 'region', 'title': 'Faction region (ex. "the Moon")'},
            {'key': 'tokens', 'title': 'Tokens (ex. "Craters")'},
            {'key': 'custom', 'title': 'Other Custom (ex. "Cursed Tomes")'},
            {'key': 'menus', 'title': 'Menu Design'},
            {'key': 'unit', 'title': 'Unit'}
        ]
        section_label = next((s['title'] for s in section_titles if s['key'] == section), section)

        now = int(time.time())

        with WRITE_LOCK:
            # Save answers
            if "claudeQA" not in entity:
                entity["claudeQA"] = {}
            if section not in entity["claudeQA"]:
                entity["claudeQA"][section] = {"questions": "", "answers": "", "updated": 0}

            # Clean up whitespace-only strings for consistency
            entity["claudeQA"][section]["answers"] = text if text.strip() else ""
            entity["claudeQA"][section]["updated"] = now
            entity["updated"] = now

            # If answers were provided and questions still exist, those questions should be cleared
            # by the admin queue agent after processing. For now just mark status appropriately.
            build = entity.get("build") or {}
            if build.get("status") == "needs_answers":
                build["status"] = "requested"
            atomic_write(entity_file, entity)

            # Create request
            requests_file = self.server.data_dir / "requests.json"
            requests_data = load_json(requests_file) or {"requests": []}
            requests = requests_data.get("requests", [])

            # Check for duplicate (same text, section, and entity)
            key = "fid" if entity_type == "faction" else "uid"
            for existing in requests:
                if (existing.get("type") == "answers" and
                    existing.get(key) == fid_or_uid and
                    existing.get("status") == "open" and
                    existing.get("data", {}).get("section") == section and
                    existing.get("text") == text):
                    # Return existing
                    self.send_json(existing)
                    return

            req_id = f"r_{secrets.token_urlsafe(6)}"
            request = {
                "id": req_id,
                "type": "answers",
                key: fid_or_uid,
                entity_type: entity_name,
                "user": username,
                "status": "open",
                "created": now,
                "updated": now,
                "text": text,
                "data": {"section": section}
            }
            requests.append(request)
            requests_data["requests"] = requests
            atomic_write(requests_file, requests_data)
            # Every designer prompt also goes into the admin console's Claude terminal log
            self.add_terminal_entry("design answers", self.display_name(username),
                                    f"Answered questions on {section_label} section: {text}" if text else f"Answered questions on {section_label} section",
                                    "Waiting to be picked up.", ref=req_id, designObject=entity_name)

            # Write queue line to console queue file
            queue_written = False
            try:
                clean_name = entity_name.replace('\n', ' ').replace('[', '').replace(']', '')
                timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
                display_user = self.display_name(username)
                queue_line = f"[{timestamp}] DESIGN-ANSWERS {req_id}: {display_user} answered Claude's questions on the \"{section_label}\" section of {clean_name} (designer {entity_type} id {fid_or_uid}, section {section}). Read the questions and answers with tickers/designer-admin.py qa {fid_or_uid} {section}.\n"
                with open(self.server.console_queue_path, 'a') as f:
                    f.write(queue_line)
                queue_written = True
            except OSError:
                pass

            if queue_written:
                request["status"] = "notified"
                requests_data["requests"] = requests
                atomic_write(requests_file, requests_data)

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

    def handle_create_unit_request(self, uid: str):
        """POST /designer/api/units/<uid>/request"""
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

        valid_types = ['build', 'bug']
        if req_type not in valid_types:
            self.send_error_json(f"Invalid request type. Must be one of: {', '.join(valid_types)}")
            return

        unit = self.load_unit(uid)
        if not unit:
            self.send_error_json("Unit not found", 404)
            return

        if unit["owner"] != username:
            self.send_error_json("Forbidden", 403)
            return

        # Load requests
        requests_file = self.server.data_dir / "requests.json"
        requests_data = load_json(requests_file) or {"requests": []}
        requests = requests_data.get("requests", [])

        # Check for duplicate (same type + uid + data)
        for existing in requests:
            if (existing.get("type") == req_type and
                existing.get("uid") == uid and
                existing.get("status") in ("open", "notified") and
                existing.get("data") == data):
                # Return existing
                self.send_json(existing)
                return

        # Create new request
        now = int(time.time())
        req_id = f"r_{secrets.token_urlsafe(6)}"

        row = (unit.get("design", {}).get("units", {}).get("rows") or [{}])[0]
        unit_name = row.get("name") or "Unnamed Unit"

        request = {
            "id": req_id,
            "type": req_type,
            "uid": uid,
            "kind": "unit",
            "unit_name": unit_name,
            "user": username,
            "status": "open",
            "created": now,
            "updated": now,
            "text": text,
            "data": data,
            "designObjectName": unit_name
        }

        with WRITE_LOCK:
            requests.append(request)
            requests_data["requests"] = requests
            atomic_write(requests_file, requests_data)
            # Every designer prompt also goes into the admin console's Claude terminal log
            self.add_terminal_entry(self.terminal_type(request), self.display_name(username),
                                    text or f"{req_type} request for unit {unit_name}",
                                    "Waiting to be picked up.", ref=req_id, designObject=unit_name)

            # Write to console queue
            queue_written = False
            try:
                clean_name = unit_name.replace('\n', ' ').replace('[', '').replace(']', '')
                timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
                display_user = self.display_name(username)
                if req_type == "build":
                    queue_line = f"[{timestamp}] UNIT-BUILD {req_id}: Build the neutral unit \"{clean_name}\" designed by {display_user} into the homebrew build (designer unit id {uid}).\n"
                elif req_type == "bug":
                    queue_line = f"[{timestamp}] UNIT-BUG {req_id}: Bug report for unit \"{clean_name}\" from {display_user} (designer unit id {uid}).\n"
                else:
                    queue_line = None

                if queue_line:
                    with open(self.server.console_queue_path, 'a') as f:
                        f.write(queue_line)
                    queue_written = True
            except OSError:
                pass

            if queue_written:
                request["status"] = "notified"
                requests_data["requests"] = requests
                atomic_write(requests_file, requests_data)

            # Update unit build status (only for build requests)
            if req_type == "build":
                unit["build"] = unit.get("build", {
                    "status": "none",
                    "liveVersion": None,
                    "requestedAt": None,
                    "builtAt": None
                })
                unit["build"]["status"] = "requested"
                unit["build"]["requestedAt"] = now
                atomic_write(self.units_dir() / uid / "unit.json", unit)

            # Add bug to bugHistory
            if req_type == "bug":
                if "bugHistory" not in unit:
                    unit["bugHistory"] = []
                bug_entry = {
                    "bugNumber": req_id,
                    "submittedAt": now,
                    "description": data.get("description", ""),
                    "response": None,
                    "respondedAt": None
                }
                unit["bugHistory"].append(bug_entry)
                atomic_write(self.units_dir() / uid / "unit.json", unit)

        self.send_json(request)

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
            if len(parts) >= 8 and parts[7] == 'qa':
                self.handle_admin_get_qa(fid, 'faction')
            else:
                self.handle_admin_get_faction(fid)
        elif endpoint == 'view-faction' and len(parts) >= 7:
            self.handle_admin_view_faction(parts[6])
        elif endpoint == 'units' and len(parts) >= 7:
            uid = parts[6]
            if len(parts) >= 8 and parts[7] == 'qa':
                self.handle_admin_get_qa(uid, 'unit')
            else:
                self.handle_admin_get_unit(uid)
        elif endpoint == 'maps' and len(parts) >= 7:
            mid = parts[6]
            if len(parts) >= 8 and parts[7] == 'qa':
                self.handle_admin_get_qa(mid, 'map')
            else:
                self.handle_admin_get_map(mid)
        elif endpoint == 'view-map' and len(parts) >= 7:
            self.handle_admin_view_map(parts[6])
        elif endpoint == 'image-usage':
            self.handle_admin_image_usage()
        elif endpoint == 'terminal-log':
            with TERMINAL_LOCK:
                path = self.server.data_dir / "terminal-log.json"
                log = load_json(path) or {"entries": []}
                if number_terminal_entries(log):
                    atomic_write(path, log)
            self.send_json({"entries": sorted(log.get("entries", []), key=lambda e: e.get("at", 0), reverse=True)})
        elif endpoint == 'agent-output':
            self.handle_admin_agent_output()
        elif endpoint == 'meta-agent-output':
            self.handle_meta_agent_output()
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
                elif action == 'stability':
                    self.handle_admin_stability(fid)
                elif action == 'live-game-versions':
                    self.handle_admin_live_game_versions(fid)
                elif action == 'viewers':
                    self.handle_admin_viewers(fid)
                elif action == 'editors':
                    self.handle_admin_editors(fid)
                elif action == 'qa':
                    self.handle_admin_post_qa(fid, 'faction')
                elif action == 'submit-note':
                    self.handle_admin_submit_note(fid, 'faction')
                else:
                    self.send_error_json("Unknown admin endpoint", 404)
            else:
                self.send_error_json("Invalid admin path", 400)
        elif endpoint == 'units' and len(parts) >= 7:
            uid = parts[6]
            if len(parts) >= 8:
                action = parts[7]
                if action == 'patch':
                    self.handle_admin_patch_unit(uid)
                elif action == 'build-status':
                    self.handle_admin_unit_build_status(uid)
                elif action == 'qa':
                    self.handle_admin_post_qa(uid, 'unit')
                elif action == 'submit-note':
                    self.handle_admin_submit_note(uid, 'unit')
                else:
                    self.send_error_json("Unknown admin endpoint", 404)
            else:
                self.send_error_json("Invalid admin path", 400)
        elif endpoint == 'maps' and len(parts) >= 7:
            mid = parts[6]
            if len(parts) >= 8:
                action = parts[7]
                if action == 'patch':
                    self.handle_admin_patch_map(mid)
                elif action == 'build-status':
                    self.handle_admin_map_build_status(mid)
                elif action == 'qa':
                    self.handle_admin_post_qa(mid, 'map')
                elif action == 'submit-note':
                    self.handle_admin_submit_note(mid, 'map')
                else:
                    self.send_error_json("Unknown admin endpoint", 404)
            else:
                self.send_error_json("Invalid admin path", 400)
        elif endpoint == 'meta-agent-prompt':
            self.handle_meta_agent_prompt()
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
                "factions": user_factions,
                "units": [self.unit_summary(u) for _, u in self.iter_units() if u.get("owner") == username],
                "maps": [self.map_summary(m) for _, m in self.iter_maps() if m.get("owner") == username]
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
        delete_maps = body.get('maps', [])

        with WRITE_LOCK:
            # Delete factions (except base factions)
            factions_dir = self.server.data_dir / "factions"
            deleted_fids = set()

            for fid in delete_factions:
                if not isinstance(fid, str) or not re.fullmatch(r'[A-Za-z0-9_-]+', fid):
                    continue
                faction_dir = factions_dir / fid
                if faction_dir.exists():
                    faction_file = faction_dir / "faction.json"
                    if faction_file.exists():
                        faction = load_json(faction_file)
                        # Never delete base factions
                        if self.is_base_faction(faction):
                            continue
                    import shutil
                    shutil.rmtree(faction_dir)
                    deleted_fids.add(fid)

            # Delete maps
            maps_dir = self.maps_dir()
            for mid in delete_maps:
                if not isinstance(mid, str) or not re.fullmatch(r'[A-Za-z0-9_-]+', mid):
                    continue
                map_dir = maps_dir / mid
                if map_dir.exists():
                    import shutil
                    shutil.rmtree(map_dir)

            # Delete users and their factions/units/maps
            users_file = self.server.data_dir / "users.json"
            users_data = load_json(users_file) or {"users": {}}
            users = users_data.get("users", {})

            for username in delete_users:
                username_lc = username.lower()
                if username_lc in users:
                    # Find and delete all user's factions (except base factions)
                    if factions_dir.exists():
                        for fid_dir in list(factions_dir.iterdir()):
                            if not fid_dir.is_dir():
                                continue
                            faction_file = fid_dir / "faction.json"
                            if faction_file.exists():
                                faction = load_json(faction_file)
                                # Never delete base factions
                                if self.is_base_faction(faction):
                                    continue
                                if faction.get("owner") == username_lc:
                                    import shutil
                                    shutil.rmtree(fid_dir)
                                    deleted_fids.add(fid_dir.name)

                    # ...and their neutral units
                    for u_dir, unit in list(self.iter_units()):
                        if unit.get("owner") == username_lc:
                            import shutil
                            shutil.rmtree(u_dir)

                    # ...and their maps
                    for m_dir, map_obj in list(self.iter_maps()):
                        if map_obj.get("owner") == username_lc:
                            import shutil
                            shutil.rmtree(m_dir)

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

        # Neutral units keep their images too
        for _, unit in self.iter_units():
            self.collect_images_from_json(unit, referenced)

        # Maps keep their images too
        for _, map_obj in self.iter_maps():
            self.collect_images_from_json(map_obj, referenced)

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

        for fid_dir in (factions_dir.iterdir() if factions_dir.exists() else []):
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

        for _, unit in self.iter_units():
            if unit.get("owner") == username:
                self.collect_images_from_json(unit, user_images)

        for _, map_obj in self.iter_maps():
            if map_obj.get("owner") == username:
                self.collect_images_from_json(map_obj, user_images)

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
            self.sync_build_status(request, status)
            default = {"in_progress": "Being worked on now.", "notified": "Owner notified.",
                       "done": "Done.", "cancelled": "Cancelled.", "open": "Waiting to be picked up."}
            self.update_terminal_entry(rid, default.get(status, status), only_if_default=True)

            # Log admin status changes to terminal
            if status in ("done", "cancelled"):
                design_name = request.get("designObjectName", request.get("faction") or request.get("mapName") or request.get("unit_name") or "Unknown")
                req_type = request.get("type", "request")
                self.add_terminal_entry("admin", "admin",
                                       f"Mark {req_type} for {design_name} as {status}",
                                       f"{default.get(status, status)}", ref=rid, designObject=design_name)

            # If marking bug request as done, update bugHistory with response
            if status == "done" and request.get("type") == "bug":
                response_text = body.get('response', '')
                self.update_bug_history_response(request, response_text)

        self.send_json(request)

    # ---- Simple Update: fixed numbers/text pushed straight to the build (no ticker) ----
    # Built factions read their fixed numbers from GET /designer/api/live/<ACR>/values.
    # Each push bumps "rev"; a game pins the rev it started with (?rev=N) so replays never change.
    SIMPLE_UPDATE_NUMBER_FIELDS = {'qty', 'cost', 'effect', 'costB', 'effectB', 'cost2', 'effect2', 'costB2', 'effectB2', 'power', 'aeStart', 'awakenPower', 'dice', 'pains', 'kills', 'num'}
    # Text fields pushed by the "Fixed Text" table (unit/SB/UFA names and text, SBR text) - see Rules.fixedText in app.js
    SIMPLE_UPDATE_TEXT_FIELDS = {'name', 'text', 'shortText', 'nameB', 'textB', 'name2', 'text2', 'nameB2', 'textB2'}
    SIMPLE_UPDATE_FIELDS = SIMPLE_UPDATE_NUMBER_FIELDS | SIMPLE_UPDATE_TEXT_FIELDS

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
            # Fallback for factions built before liveVersion was numeric (e.g. "HB 9267656"):
            # find the version that was actually built. requestedAt is when the designer's
            # edits were snapshotted for Claude to build from, so the version that was
            # "current" at that moment is the one that got built - not whatever "current"
            # is now, which may have moved on with further unbuilt edits since.
            if isinstance(live_version, str) and not live_version.isdigit():
                anchor = faction.get("build", {}).get("requestedAt") or faction.get("build", {}).get("builtAt")
                resolved = None
                if anchor:
                    for v in sorted(faction.get("versions", []), key=lambda v: v.get("n", 0)):
                        if v.get("created", 0) <= anchor and not v.get("deleted"):
                            resolved = v.get("n")
                if resolved is None:
                    return None
                v_file = self.server.data_dir / "factions" / fid / "v" / f"{resolved}.json"
                if not v_file.exists():
                    return None
                live_version = resolved
            else:
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

        # Handle image_swap type
        if data.get('type') == 'image_swap':
            return self.handle_image_swap_push(fid, faction, username, data)

        # Handle numeric and text field updates
        section, row_id, field = data.get('section'), data.get('rowId'), data.get('field')
        if field not in self.SIMPLE_UPDATE_FIELDS or not isinstance(section, str) or not section.isalnum() \
                or (row_id is not None and not (isinstance(row_id, str) and re.fullmatch(r'[A-Za-z0-9_-]+', row_id))):
            self.send_error_json("That value can't be pushed as a simple update.")
            return
        path = self.simple_update_path(section, row_id, field)
        # The value always comes from the saved design, never from the browser
        value = self.get_path_value(faction["design"], path)
        if field in self.SIMPLE_UPDATE_TEXT_FIELDS:
            if not isinstance(value, str) or not value:
                self.send_error_json("That value isn't plain text in the design, so it can't be pushed.")
                return
        elif isinstance(value, bool) or not isinstance(value, (int, float)):
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
            # Every designer prompt also goes into the admin console's Claude terminal log
            self.add_terminal_entry("design update", self.display_name(username), request["text"],
                                    "Saved for the build; reaches the game after faction-values.py sync && apply --deploy (no Claude needed).", ref=request["id"],
                                    designObject=faction['name'], faction=faction['name'])
        self.send_json(request)

    def handle_image_swap_push(self, fid: str, faction: Dict, username: str, data: Dict):
        """Push image swap: copy image to build's webp/images folder and mark as ready."""
        filename = data.get('filename', '')
        image_id = data.get('imageId', '')

        # Validate filename format: acr-name.webp
        if not re.fullmatch(r'[a-z0-9]{2,3}-[a-z0-9\-]+\.webp', filename, re.IGNORECASE):
            self.send_error_json("Invalid filename. Use format: acronym-name.webp (e.g., fm-glyph.webp)")
            return

        # Validate image_id
        if not re.fullmatch(r'[a-f0-9]+\.(webp|png|jpg)', image_id):
            self.send_error_json("Invalid image ID")
            return

        # Source image
        source_image = self.server.data_dir / "images" / image_id
        if not source_image.exists():
            self.send_error_json("Source image not found")
            return

        now = int(time.time())
        with WRITE_LOCK:
            # Create imageSwaps directory if needed
            swap_dir = self.server.data_dir / "factions" / fid / "imageSwaps"
            swap_dir.mkdir(parents=True, exist_ok=True)

            # Copy image to imageSwaps folder
            dest_image = swap_dir / filename
            try:
                import shutil
                shutil.copy2(source_image, dest_image)
            except Exception as e:
                self.send_error_json(f"Failed to copy image: {str(e)}")
                return

            # Log as a completed image swap request
            requests_file = self.server.data_dir / "requests.json"
            requests_data = load_json(requests_file) or {"requests": []}
            request = {
                "id": f"r_{secrets.token_urlsafe(6)}", "type": "simple_update", "fid": fid,
                "faction": faction["name"], "acronym": faction["acronym"], "user": username,
                "status": "done", "created": now, "updated": now,
                "text": f"Faction {faction['name']} image swap: {filename}",
                "data": {"type": "image_swap", "filename": filename, "imageId": image_id},
            }
            requests_data.setdefault("requests", []).append(request)
            atomic_write(requests_file, requests_data)
            # Every designer prompt also goes into the admin console's Claude terminal log
            self.add_terminal_entry("design update", self.display_name(username), request["text"],
                                    "Saved to imageSwaps; needs faction-values.py sync && apply --deploy to go live.",
                                    ref=request["id"], designObject=faction['name'], faction=faction['name'])

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

        response = dict(faction)
        response["pendingRequests"] = self.get_pending_requests_for_entity(fid, "faction")
        # Same builtDesign/liveValues the designer page itself gets (handle_get_faction) and the
        # admin read-only viewer gets (handle_admin_view_faction) - without this, Claude's own
        # admin CLI looked null here even when the real page had a built version, which caused a
        # false "builtDesign is null" diagnosis for a bug that was actually just a deploy lag.
        response["builtDesign"] = self.built_design_with_overrides(fid, faction)
        response["liveValues"] = self.load_live_values(fid)
        # Add spellbook guidance to design for Claude
        if "design" in response:
            response["design"]["spellbookGuidance"] = compute_spellbook_guidance(response["design"])
        self.send_json(response)

    def get_pending_requests_for_entity(self, entity_id: str, entity_type: str = "faction"):
        """Get all pending requests for an entity (faction/unit/map)"""
        requests_file = self.server.data_dir / "requests.json"
        requests_data = load_json(requests_file) or {"requests": []}
        all_requests = requests_data.get("requests", [])

        pending = []
        for req in all_requests:
            # Match based on entity type
            if entity_type == "faction" and req.get("fid") == entity_id:
                pass
            elif entity_type == "unit" and req.get("uid") == entity_id:
                pass
            elif entity_type == "map" and req.get("mid") == entity_id:
                pass
            else:
                continue

            # Include if status is pending
            if req.get("status") in ("open", "notified", "requested", "in_progress"):
                pending.append({
                    "id": req.get("id"),
                    "type": req.get("type"),
                    "status": req.get("status"),
                    "text": (req.get("text") or f"{req.get('type')} request")[:200],
                    "created": req.get("created")
                })

        return pending

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
        response["buildAttempted"] = self.has_build_attempt(faction, fid, "faction")
        response["pendingRequests"] = self.get_pending_requests_for_entity(fid, "faction")
        if "claudeQA" not in response:
            response["claudeQA"] = {}
        # Add spellbook guidance to design for Claude
        if "design" in response:
            response["design"]["spellbookGuidance"] = compute_spellbook_guidance(response["design"])
        # Admin inspector: expose build metadata
        if "build" in faction:
            response["requestId"] = faction["build"].get("requestId")
            response["submittedAt"] = faction["build"].get("requestedAt")
            response["buildHistory"] = faction["build"].get("history", [])
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

            # Separate admin notes from design patches
            admin_note_ops = []
            design_ops = []

            for op in ops:
                path = op.get('path', '')
                if path.endswith('.adminNotes'):
                    admin_note_ops.append(op)
                else:
                    design_ops.append(op)

            # Apply admin notes directly (not through versioning)
            for op in admin_note_ops:
                # Don't leave a stub {adminNotes} section in an older design that lacks it
                self.backfill_section(faction["design"], op.get('path', '').split('.')[0], None)
                if not self.apply_op_to_design(faction["design"], op):
                    return

            # Apply design patches through normal versioning logic
            for op in design_ops:
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

        valid_statuses = ['requested', 'in_progress', 'needs_answers', 'built', 'none']
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

            if status == 'built':
                # If no version provided or version is not numeric, use the faction's current version
                if not version or (isinstance(version, str) and not version.isdigit()):
                    version = faction.get("current")
                if version:
                    build["liveVersion"] = version
                    build["builtAt"] = int(time.time())

                    # Add to history if not already there
                    if not any(h.get("version") == version for h in build.get("history", [])):
                        build.setdefault("history", []).append({
                            "version": version,
                            "builtAt": build["builtAt"]
                        })

                    # Set stability to alpha if not already set
                    if "stability" not in faction:
                        faction["stability"] = "alpha"

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

    def handle_admin_stability(self, fid: str):
        """POST admin/factions/<fid>/stability"""
        body = self.read_json_body()
        if not body:
            return

        stability = body.get('stability')
        valid_values = ['alpha', 'beta', 'stable']
        if stability not in valid_values:
            self.send_error_json(f"Invalid stability. Must be one of: {', '.join(valid_values)}")
            return

        with WRITE_LOCK:
            faction = self.load_faction(fid)
            if not faction:
                self.send_error_json("Faction not found", 404)
                return

            faction["stability"] = stability
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

    def handle_admin_get_unit(self, uid: str):
        """GET admin/units/<uid>"""
        unit = self.load_unit(uid)
        if not unit:
            self.send_error_json("Unit not found", 404)
            return
        response = dict(unit)
        response["pendingRequests"] = self.get_pending_requests_for_entity(uid, "unit")
        self.send_json(response)

    def handle_admin_unit_build_status(self, uid: str):
        """POST admin/units/<uid>/build-status"""
        body = self.read_json_body()
        if not body:
            return

        status = body.get('status')
        version = body.get('version')

        valid_statuses = ['requested', 'in_progress', 'needs_answers', 'built', 'none']
        if status not in valid_statuses:
            self.send_error_json(f"Invalid status. Must be one of: {', '.join(valid_statuses)}")
            return

        with WRITE_LOCK:
            unit = self.load_unit(uid)
            if not unit:
                self.send_error_json("Unit not found", 404)
                return

            build = unit.setdefault("build", {
                "status": "none",
                "liveVersion": None,
                "requestedAt": None,
                "builtAt": None,
                "history": []
            })

            build["status"] = status

            if status == 'built':
                # If no version provided or version is not numeric, use the unit's current version
                if not version or (isinstance(version, str) and not version.isdigit()):
                    version = unit.get("current")
                if version:
                    build["liveVersion"] = version
                    build["builtAt"] = int(time.time())

                    # Add to history if not already there
                    if not any(h.get("version") == version for h in build.get("history", [])):
                        build.setdefault("history", []).append({
                            "version": version,
                            "builtAt": build["builtAt"]
                        })

            unit["updated"] = int(time.time())
            unit_file = self.units_dir() / uid / "unit.json"
            atomic_write(unit_file, unit)

        self.send_json({"ok": True})

    def handle_admin_get_map(self, mid: str):
        """GET admin/maps/<mid>"""
        map_obj = self.load_map(mid)
        if not map_obj:
            self.send_error_json("Map not found", 404)
            return
        response = dict(map_obj)
        response["pendingRequests"] = self.get_pending_requests_for_entity(mid, "map")
        self.send_json(response)

    def handle_admin_view_map(self, mid: str):
        """GET admin/view-map/<mid> -- same shape the designer page gets, always read only"""
        map_obj = self.load_map(mid)
        if not map_obj:
            self.send_error_json("Map not found", 404)
            return

        response = dict(map_obj)
        response["readOnly"] = True
        response["adminView"] = True
        response["ownerName"] = self.display_name(map_obj["owner"])
        response["buildAttempted"] = self.has_build_attempt(map_obj, mid, "map")
        response["pendingRequests"] = self.get_pending_requests_for_entity(mid, "map")
        if "claudeQA" not in response:
            response["claudeQA"] = {}
        self.send_json(response)

    def handle_admin_patch_unit(self, uid: str):
        """POST admin/units/<uid>/patch"""
        body = self.read_json_body()
        if not body:
            return

        ops = body.get('ops', [])
        if not isinstance(ops, list):
            self.send_error_json("ops must be an array")
            return

        with WRITE_LOCK:
            unit = self.load_unit(uid)
            if not unit:
                self.send_error_json("Unit not found", 404)
                return

            # Separate admin notes from design patches
            admin_note_ops = []
            design_ops = []

            for op in ops:
                path = op.get('path', '')
                if path.endswith('.adminNotes'):
                    admin_note_ops.append(op)
                else:
                    design_ops.append(op)

            # Apply admin notes directly (not through versioning)
            for op in admin_note_ops:
                # Don't leave a stub {adminNotes} section in an older design that lacks it
                self.backfill_section(unit["design"], op.get('path', '').split('.')[0], None)
                if not self.apply_op_to_design(unit["design"], op):
                    return

            # Apply design patches through normal versioning logic
            for op in design_ops:
                if not self.apply_patch_op(unit, op, uid):
                    return

            unit["updated"] = int(time.time())
            unit_file = self.server.data_dir / "units" / uid / "unit.json"
            atomic_write(unit_file, unit)

            # Always rewrite current version snapshot
            v_file = self.server.data_dir / "units" / uid / "v" / f"{unit['current']}.json"
            v_file.parent.mkdir(parents=True, exist_ok=True)
            atomic_write(v_file, unit["design"])

            self.send_json({"ok": True})

    def handle_admin_patch_map(self, mid: str):
        """POST admin/maps/<mid>/patch"""
        body = self.read_json_body()
        if not body:
            return

        ops = body.get('ops', [])
        if not isinstance(ops, list):
            self.send_error_json("ops must be an array")
            return

        with WRITE_LOCK:
            map_obj = self.load_map(mid)
            if not map_obj:
                self.send_error_json("Map not found", 404)
                return

            # Separate admin notes from design patches
            admin_note_ops = []
            design_ops = []

            for op in ops:
                path = op.get('path', '')
                if path.endswith('.adminNotes'):
                    admin_note_ops.append(op)
                else:
                    design_ops.append(op)

            # Apply admin notes directly (not through versioning)
            for op in admin_note_ops:
                # Don't leave a stub {adminNotes} section in an older design that lacks it
                self.backfill_section(map_obj["design"], op.get('path', '').split('.')[0], self.new_map_design())
                if not self.apply_op_to_design(map_obj["design"], op):
                    return

            # Apply design patches through normal versioning logic
            for op in design_ops:
                if not self.apply_map_patch_op(map_obj, op, mid):
                    return

            map_obj["updated"] = int(time.time())
            map_file = self.maps_dir() / mid / "map.json"
            atomic_write(map_file, map_obj)

            # Always rewrite current version snapshot
            v_file = self.maps_dir() / mid / "v" / f"{map_obj['current']}.json"
            atomic_write(v_file, map_obj["design"])

        self.send_json({
            "current": map_obj["current"],
            "maxVersion": map_obj["maxVersion"],
            "versions": map_obj["versions"],
            "session": map_obj["session"],
            "updated": map_obj["updated"]
        })

    def handle_admin_map_build_status(self, mid: str):
        """POST admin/maps/<mid>/build-status"""
        body = self.read_json_body()
        if not body:
            return

        status = body.get('status')
        version = body.get('version')

        valid_statuses = ['requested', 'in_progress', 'needs_answers', 'built', 'none']
        if status not in valid_statuses:
            self.send_error_json(f"Invalid status. Must be one of: {', '.join(valid_statuses)}")
            return

        with WRITE_LOCK:
            map_obj = self.load_map(mid)
            if not map_obj:
                self.send_error_json("Map not found", 404)
                return

            build = map_obj.setdefault("build", {
                "status": "none",
                "liveVersion": None,
                "requestedAt": None,
                "builtAt": None,
                "history": []
            })

            build["status"] = status

            if status == 'built':
                # If no version provided or version is not numeric, use the map's current version
                if not version or (isinstance(version, str) and not version.isdigit()):
                    version = map_obj.get("current")
                if version:
                    build["liveVersion"] = version
                    build["builtAt"] = int(time.time())

                    # Add to history if not already there
                    if not any(h.get("version") == version for h in build.get("history", [])):
                        build.setdefault("history", []).append({
                            "version": version,
                            "builtAt": build["builtAt"]
                        })

            map_obj["updated"] = int(time.time())
            map_file = self.maps_dir() / mid / "map.json"
            atomic_write(map_file, map_obj)

        self.send_json({"ok": True})

    # ── Helpers ──────────────────────────────────────────────────────────────────

    # ---- Claude Q&A ----

    def handle_admin_get_qa(self, entity_id: str, entity_type: str):
        """GET admin/factions/<fid>/qa or admin/units/<uid>/qa or admin/maps/<mid>/qa -> {claudeQA}"""
        if entity_type == "faction":
            entity = self.load_faction(entity_id)
        elif entity_type == "unit":
            entity = self.load_unit(entity_id)
        else:  # map
            entity = self.load_map(entity_id)

        if not entity:
            self.send_error_json(f"{entity_type.capitalize()} not found", 404)
            return

        self.send_json({"claudeQA": entity.get("claudeQA", {})})

    def handle_admin_post_qa(self, entity_id: str, entity_type: str):
        """POST admin/factions/<fid>/qa or admin/units/<uid>/qa or admin/maps/<mid>/qa {section, questions?, answers?}
        Sets whichever fields are given (empty string clears)."""
        body = self.read_json_body()
        if body is None:
            return

        section = body.get('section', '').strip()
        if not section:
            self.send_error_json("section is required")
            return

        if entity_type == "faction":
            entity = self.load_faction(entity_id)
            if not entity:
                self.send_error_json("Faction not found", 404)
                return
            entity_file = self.server.data_dir / "factions" / entity_id / "faction.json"
        elif entity_type == "unit":
            entity = self.load_unit(entity_id)
            if not entity:
                self.send_error_json("Unit not found", 404)
                return
            entity_file = self.units_dir() / entity_id / "unit.json"
        else:  # map
            entity = self.load_map(entity_id)
            if not entity:
                self.send_error_json("Map not found", 404)
                return
            entity_file = self.maps_dir() / entity_id / "map.json"

        now = int(time.time())

        with WRITE_LOCK:
            if "claudeQA" not in entity:
                entity["claudeQA"] = {}
            if section not in entity["claudeQA"]:
                entity["claudeQA"][section] = {"questions": "", "answers": "", "updated": 0}

            # Set whichever fields are provided
            if "questions" in body:
                entity["claudeQA"][section]["questions"] = body["questions"] or ""
            if "answers" in body:
                entity["claudeQA"][section]["answers"] = body["answers"] or ""

            entity["claudeQA"][section]["updated"] = now
            entity["updated"] = now
            atomic_write(entity_file, entity)

        self.send_json({"claudeQA": entity["claudeQA"]})

    def handle_admin_submit_note(self, entity_id: str, entity_type: str):
        """POST admin/factions/<fid>/submit-note or admin/units/<uid>/submit-note or admin/maps/<mid>/submit-note
        {section, note} -> Create immediate high-priority task in admin queue"""
        body = self.read_json_body()
        if body is None:
            return

        section = body.get('section', '').strip()
        note = body.get('note', '').strip()

        if not section:
            self.send_error_json("section is required")
            return
        if not note:
            self.send_error_json("note is required")
            return

        # Load entity to get its name
        if entity_type == "faction":
            entity = self.load_faction(entity_id)
            entity_name = entity.get('name', entity_id) if entity else entity_id
            type_label = 'Faction'
        elif entity_type == "unit":
            entity = self.load_unit(entity_id)
            entity_name = entity.get('name', entity_id) if entity else entity_id
            type_label = 'Unit'
        else:  # map
            entity = self.load_map(entity_id)
            entity_name = entity.get('name', entity_id) if entity else entity_id
            type_label = 'Map'

        if not entity:
            self.send_error_json(f"{type_label} not found", 404)
            return

        # Create queue entry in ~/.cw-admin-queue/pending/
        queue_dir = Path.home() / '.cw-admin-queue' / 'pending'
        queue_dir.mkdir(parents=True, exist_ok=True)

        # Generate timestamp and random suffix
        timestamp = int(time.time() * 1000)
        random_suffix = secrets.token_hex(2)
        queue_file = queue_dir / f"{timestamp}-{random_suffix}"

        # Format: ADMIN-NOTE {entity_id}: [Type: {type}] [Section: {section}] IMMEDIATE: {note}
        queue_content = f"ADMIN-NOTE {entity_id}: [{type_label}: {entity_name}] [Section: {section}] IMMEDIATE: {note}"

        with WRITE_LOCK:
            with open(queue_file, 'w', encoding='utf-8') as f:
                f.write(queue_content)

        self.send_json({"success": True, "queue_file": queue_file.name, "entity_id": entity_id, "section": section})

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

    def handle_admin_editors(self, fid: str):
        """POST admin/factions/<fid>/editors {editors:[username...]} -> edit access for those users"""
        body = self.read_json_body()
        if body is None:
            return
        editors = body.get('editors', [])
        if not isinstance(editors, list):
            self.send_error_json("editors must be an array")
            return
        users = (load_json(self.server.data_dir / "users.json") or {}).get("users", {})
        editors = [str(e).strip().lower() for e in editors]
        missing = [e for e in editors if e not in users]
        if missing:
            self.send_error_json(f"No such user: {', '.join(missing)}")
            return
        with WRITE_LOCK:
            faction = self.load_faction(fid)
            if not faction:
                self.send_error_json("Faction not found", 404)
                return
            faction["editors"] = [e for e in dict.fromkeys(editors) if e != faction["owner"]]
            atomic_write(self.server.data_dir / "factions" / fid / "faction.json", faction)
        self.send_json({"id": fid, "editors": faction["editors"]})

    def handle_admin_import_faction(self):
        """POST admin/import-faction {owner, name, acronym, design, built:bool, viewers:[], base:bool}
        Creates a design for a user from a faction that already exists in code (no reserved-acronym
        check; still refuses an acronym another design uses unless it's a base faction being replaced).
        built=true marks version 1 as the live build. base=true creates a base faction (owner forced to "base",
        viewers ignored); if a base faction with the same acronym exists, replaces it in place (new version)."""
        body = self.read_json_body()
        if body is None:
            return
        is_base = bool(body.get('base'))
        owner = "base" if is_base else str(body.get('owner', '')).strip().lower()
        name = str(body.get('name', '')).strip()
        acronym = str(body.get('acronym', '')).strip().upper()
        design = body.get('design')

        users = (load_json(self.server.data_dir / "users.json") or {}).get("users", {})
        if not is_base and owner not in users:
            self.send_error_json("No such user")
            return
        if len(name) < 5 or not re.match(r'^[A-Z0-9]{2,3}$', acronym):
            self.send_error_json("Name must be 5+ characters and acronym 2-3 letters or digits")
            return

        # Keep reserved acronyms reserved for base factions
        if acronym in self.server.reserved_acronyms and not is_base:
            self.send_error_json(f"Acronym {acronym} is reserved")
            return

        # Get stability if provided (for imports)
        stability = body.get('stability')
        if stability and stability not in ['alpha', 'beta', 'stable']:
            self.send_error_json("stability must be alpha, beta, or stable")
            return

        base_design = self.new_design()
        if not isinstance(design, dict) or set(design) - set(base_design):
            self.send_error_json("design must be an object with only the known sections")
            return
        for key, value in base_design.items():
            design.setdefault(key, value)

        # Base factions ignore viewers (always visible to everyone read-only)
        viewers = [] if is_base else [str(v).strip().lower() for v in body.get('viewers', [])]
        if viewers and any(v not in users for v in viewers):
            self.send_error_json("A viewer is not a user")
            return

        factions_dir = self.server.data_dir / "factions"
        factions_dir.mkdir(parents=True, exist_ok=True)
        now = int(time.time())
        built = bool(body.get('built'))

        with WRITE_LOCK:
            # Check for existing base faction with same acronym (replace in place)
            existing_fid = None
            for fd in factions_dir.iterdir():
                if (fd / "faction.json").exists():
                    existing = load_json(fd / "faction.json")
                    if existing.get("acronym") == acronym:
                        if is_base and self.is_base_faction(existing):
                            # Replace this base faction in place
                            existing_fid = existing["id"]
                            break
                        elif not is_base or not self.is_base_faction(existing):
                            # Non-base collision, or user faction collision
                            self.send_error_json(f"Acronym {acronym} is already used by another design")
                            return

            # Upload images if provided (admin can inject images as part of import)
            if existing_fid:
                # Replace existing base faction: new version
                fid = existing_fid
                existing = load_json(factions_dir / fid / "faction.json")
                current = existing["current"]
                max_version = existing["maxVersion"]

                # Freeze current version
                v_file = factions_dir / fid / "v" / f"{current}.json"
                if not v_file.exists():
                    atomic_write(v_file, existing["design"])

                # Create new version
                new_n = max_version + 1
                existing["versions"].append({
                    "n": new_n,
                    "from": current,
                    "sections": [k for k in base_design if not self.is_section_empty(k, design.get(k))],
                    "created": now,
                    "deleted": False
                })
                existing["current"] = new_n
                existing["maxVersion"] = new_n
                existing["design"] = design
                existing["updated"] = now
                existing["name"] = name  # Update name too
                # Keep build status if it was built
                if built or existing.get("build", {}).get("status") == "built":
                    existing["build"]["liveVersion"] = new_n
                    existing["build"]["status"] = "built"
                    existing["build"]["builtAt"] = now
                    if not any(h.get("version") == new_n for h in existing["build"].get("history", [])):
                        existing.setdefault("build", {}).setdefault("history", []).append({
                            "version": new_n,
                            "builtAt": now
                        })
                faction = existing
                atomic_write(factions_dir / fid / "faction.json", faction)
                atomic_write(factions_dir / fid / "v" / f"{new_n}.json", design)
            else:
                # Create new faction
                fid = secrets.token_urlsafe(9).replace('_', '').replace('-', '').lower()[:12]
                faction = {
                    "id": fid, "owner": owner, "name": name, "acronym": acronym,
                    "created": now, "updated": now, "current": 1, "maxVersion": 1,
                    "versions": [{"n": 1, "from": None, "sections": [k for k in base_design if not self.is_section_empty(k, design.get(k))],
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
                if is_base:
                    faction["base"] = True
                if stability:
                    faction["stability"] = stability
                (factions_dir / fid / "v").mkdir(parents=True, exist_ok=True)
                atomic_write(factions_dir / fid / "faction.json", faction)
                atomic_write(factions_dir / fid / "v" / "1.json", design)

        self.send_json(faction)

    @staticmethod
    def terminal_type(request: Dict) -> str:
        t = request.get("type")
        kind = request.get("kind")
        if t == "extract":
            if kind == "map":
                return "map extraction"
            return "design menu" if request.get("data", {}).get("target") == "menus" else "design extraction"
        if t == "bug":
            if kind == "map":
                return "map bug fix"
            elif kind == "unit":
                return "unit bug fix"
            return "design bug fix"
        if t == "build":
            if kind == "map":
                return "map build"
            elif kind == "unit":
                return "unit build"
        if t == "simple_update":
            return "design update"
        return "design build"   # build and update both change the built faction

    def add_terminal_entry(self, kind: str, user: str, prompt: str, summary: str, ref: Optional[str] = None, designObject: Optional[str] = None, faction: Optional[str] = None) -> Dict:
        """Append one row to terminal-log.json. Caller may already hold WRITE_LOCK (it is not re-entrant),
        so this uses its own lock."""
        entry = {"id": ref or f"t_{secrets.token_urlsafe(6)}", "at": int(time.time()), "type": kind,
                 "user": user, "prompt": str(prompt)[:20000], "summary": str(summary)[:20000], "defaultSummary": True}
        if designObject:
            entry["designObject"] = str(designObject)[:200]
        if faction:
            entry["faction"] = str(faction)[:200]
        with TERMINAL_LOCK:
            path = self.server.data_dir / "terminal-log.json"
            log = load_json(path) or {"entries": []}
            log.setdefault("entries", []).append(entry)
            number_terminal_entries(log)
            log["entries"] = log["entries"][-2000:]
            atomic_write(path, log)
        return entry

    def update_terminal_entry(self, entry_id: str, summary: Optional[str] = None, only_if_default: bool = False,
                              cost: Optional[float] = None, add_cost: bool = False, cost_note: Optional[str] = None) -> Optional[Dict]:
        with TERMINAL_LOCK:
            path = self.server.data_dir / "terminal-log.json"
            log = load_json(path) or {"entries": []}
            entry = next((e for e in log.get("entries", []) if e.get("id") == entry_id), None)
            if not entry or (only_if_default and not entry.get("defaultSummary")):
                return entry
            if summary is not None:
                entry["summary"] = str(summary)[:20000]
                entry["defaultSummary"] = only_if_default
            if cost is not None:
                if add_cost:
                    entry["cost"] = round(entry.get("cost", 0.0) + cost, 4)
                else:
                    entry["cost"] = round(cost, 4)
            if cost_note is not None:
                if cost_note == "":
                    entry.pop("costNote", None)
                else:
                    entry["costNote"] = str(cost_note)[:60]
            entry["updatedAt"] = int(time.time())
            atomic_write(path, log)
        return entry

    def handle_terminal_log(self):
        """GET /designer/api/terminal-log?name=<design name>: the Claude terminal log entries for one
        faction/unit/map, used by its "Terminal Log & Bug Report" screen. Requires login; scoped to the
        requested design name so one user's session can't pull every other user's terminal log."""
        username = self.verify_session()
        if not username:
            self.send_error_json("Unauthorized", 401)
            return
        name = parse_qs(urlparse(self.path).query).get('name', [''])[0]
        with TERMINAL_LOCK:
            path = self.server.data_dir / "terminal-log.json"
            log = load_json(path) or {"entries": []}
            if number_terminal_entries(log):
                atomic_write(path, log)
        entries = [e for e in log.get("entries", [])
                   if name and (e.get("faction") == name or e.get("designObject") == name)]
        self.send_json({"entries": sorted(entries, key=lambda e: e.get("at", 0), reverse=True)})

    def handle_admin_agent_output(self):
        """GET admin/agent-output: returns live JSONL output from the admin queue agent.
        Returns {running: bool, requestId: str|null, output: str}."""
        # Check if there's a running agent output file in ~/.cw-admin-queue/running/*.jsonl
        queue_dir = Path.home() / ".cw-admin-queue" / "running"
        if not queue_dir.exists():
            self.send_json({"running": False, "requestId": None, "output": ""})
            return

        # Find the newest JSONL file
        jsonl_files = sorted(queue_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not jsonl_files:
            self.send_json({"running": False, "requestId": None, "output": ""})
            return

        jsonl_file = jsonl_files[0]
        try:
            # Read the file and get the last ~200 lines or ~50KB
            with open(jsonl_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            # Limit to last 50KB
            if len(content) > 50000:
                content = content[-50000:]
                # Try to find the start of a line (skip partial line)
                newline_idx = content.find('\n')
                if newline_idx >= 0:
                    content = content[newline_idx + 1:]

            # Split into lines and keep last 200
            lines = content.split('\n')
            if len(lines) > 200:
                lines = lines[-200:]
                output = '\n'.join(lines)
            else:
                output = content.rstrip('\n')

            # Extract request ID from filename (e.g., "1791866264-001.jsonl" -> "1791866264-001")
            request_id = jsonl_file.stem

            self.send_json({
                "running": True,
                "requestId": request_id,
                "output": output
            })
        except Exception as e:
            self.send_json({
                "running": False,
                "requestId": None,
                "output": f"Error reading agent output: {str(e)}"
            })

    def handle_meta_agent_prompt(self):
        """POST admin/meta-agent-prompt: writes prompt to /tmp/meta-agent-prompts.log for pickup by meta agent watchdog."""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')

            if not body.strip():
                self.send_error_json("Empty prompt", 400)
                return

            # Write to the meta agent prompt file
            prompt_file = Path("/tmp/meta-agent-prompts.log")
            with open(prompt_file, 'w', encoding='utf-8') as f:
                f.write(body)

            self.send_json({"success": True, "message": "Prompt queued for meta agent"})
        except Exception as e:
            self.send_error_json(f"Failed to queue prompt: {str(e)}", 500)

    def handle_meta_agent_output(self):
        """GET admin/meta-agent-output?lines=N: returns recent output from /tmp/meta-agent-stdout.log."""
        # Parse query parameters
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        max_lines = int(params.get('lines', ['100'])[0])

        output_file = Path("/tmp/meta-agent-stdout.log")

        if not output_file.exists():
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write(b'(no output yet)')
            return

        try:
            with open(output_file, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()

            # Return last N lines
            if len(lines) > max_lines:
                lines = lines[-max_lines:]

            output = ''.join(lines)

            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write(output.encode('utf-8'))
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write(f"Error reading meta agent output: {str(e)}".encode('utf-8'))

    def handle_admin_terminal_log(self, entry_id: Optional[str]):
        """POST admin/terminal-log {type,user,prompt,summary,[id],[at]} adds a row;
        POST admin/terminal-log/<id> {summary?,cost?,add?,costNote?} updates that row."""
        body = self.read_json_body()
        if body is None:
            return
        if entry_id:
            summary = body.get('summary') if 'summary' in body else None
            cost = body.get('cost')
            add_cost = body.get('add', False)
            cost_note = body.get('costNote') if 'costNote' in body else None
            if cost is not None:
                if not isinstance(cost, (int, float)) or cost < 0:
                    self.send_error_json("cost must be a non-negative number", 400)
                    return
            if cost_note is not None and not isinstance(cost_note, str):
                self.send_error_json("costNote must be a string", 400)
                return
            entry = self.update_terminal_entry(entry_id, summary=summary, cost=cost, add_cost=add_cost, cost_note=cost_note)
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
                                        body.get('summary', ''), ref=body.get('id'), designObject=body.get('designObject'))
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
            "meta": {"color": None, "adminNotes": ""},
            "card": {"image": None, "glyph": None},
            "sbImages": {"mode": None, "all": None, "each": [None]*6},
            "sbImagesB": {"mode": None, "all": None, "each": [None]*6},
            "ae": {
                "enabled": False,
                "name": "",
                "acronym": "",
                "rows": [{"id": self.new_id(), "sign": "+", "kind": "fixed", "qty": None, "calc": "", "desc": ""}],
                "adminNotes": ""
            },
            "ufa": {
                "name": "",
                "phase": None,
                "type": None,
                "hasCost": False,
                "cost": None,
                "hasEffect": False,
                "effect": None,
                "text": "",
                "adminNotes": ""
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
                "aeStart": 0,
                "adminNotes": ""
            },
            "units": {"rows": [self.blank_unit(), self.blank_unit(), self.blank_unit()], "adminNotes": ""},
            "sbr": {"multiText": "", "rows": [
                {"id": self.new_id(), "text": "", "hasNum": False, "num": None, "shortText": ""} for _ in range(6)
            ], "adminNotes": ""},
            "sb": {"twoSided": False, "rows": [
                {"id": self.new_id(), "name": "", "type": None, "cost": 0, "hasEffect": False, "effect": None, "text": "",
                 "nameB": "", "typeB": None, "costB": 0, "hasEffectB": False, "effectB": None, "textB": "",
                 "dual": False, "name2": "", "type2": None, "cost2": 0, "hasEffect2": False, "effect2": None, "text2": "",
                 "dualB": False, "nameB2": "", "typeB2": None, "costB2": 0, "hasEffectB2": False, "effectB2": None,
                 "textB2": ""} for _ in range(6)
            ], "adminNotes": ""},
            # Each table starts with one blank row (same as Rules.newDesign in www/rules.js)
            "region": {"rows": [{"id": self.new_id(), "name": "", "image": None, "restrictions": "", "adjacency": ""}], "adminNotes": ""},
            "tokens": {"rows": [{"id": self.new_id(), "name": "", "qty": None, "image": None, "placement": "",
                                 "effects": "", "hasEffect": False, "effect": None}], "adminNotes": ""},
            "custom": {"rows": [{"id": self.new_id(), "name": "", "image": None, "placement": "", "usage": "",
                                 "effects": "", "hasNum": False, "num": None}], "adminNotes": ""},
            "menus": {"rows": [{"id": self.new_id(), "name": "", "section": None, "item": None, "prompted": None,
                                "title": "", "hasSubtitle": False, "subtitle": "", "button": "", "cancel": False,
                                "skip": False, "done": False, "multiSelect": False, "repeat": False, "repeatCount": "",
                                "numberPick": False, "numberMin": "", "numberMax": "", "greyedOptions": False,
                                "greyedReason": "", "infoOnly": False, "confirm": False, "confirmText": "",
                                "showPicked": False, "leadsToNext": False, "next": None, "nextTrigger": ""}], "adminNotes": ""},
            "interactions": {"rows": [
                {"id": self.new_id(), "otherFaction": "Sleeper", "abilityType": "Spellbook", "ability": "Ancient Sorcery",
                 "abilityText": "", "yourAbility": "ufa", "interactionDesc": ""},
                {"id": self.new_id(), "otherFaction": "Neutral Monsters", "abilityType": "Unit Special",
                 "ability": "Blasphemous Obeisance", "abilityText": "", "yourAbility": "", "interactionDesc": ""},
                {"id": self.new_id(), "otherFaction": "Bubastis", "abilityType": "Unit Special",
                 "ability": "Moon", "abilityText": "", "yourAbility": "", "interactionDesc": ""}
            ], "adminNotes": ""}
        }
        # Every design section ends with a free "Any custom logic or rules" box
        for key in ("ae", "ufa", "setup", "units", "sbr", "sb", "region", "tokens", "custom", "menus", "interactions"):
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
            "abilityText": "",
            "spellbook": {
                "enabled": False,
                "requirement": {"text": "", "hasNum": False, "num": None},
                "book": {"name": "", "type": None, "cost": 0, "hasEffect": False, "effect": None, "text": ""}
            }
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
    parser.add_argument('--console-queue', default='/tmp/claude-prompts.log', help='Console queue file path')

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
    server.console_queue_path = Path(args.console_queue)

    print(f"CW Faction Designer Server running on {args.host}:{args.port}", file=sys.stderr)
    print(f"Data directory: {data_dir}", file=sys.stderr)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...", file=sys.stderr)
        server.shutdown()


if __name__ == '__main__':
    main()
