#!/usr/bin/env python3
"""
Mock server for Cthulhu Wars Faction Designer
Serves www/ at /designer/ and implements a fake API for testing
"""

import http.server
import socketserver
import json
import time
import hashlib
import secrets
from urllib.parse import urlparse, parse_qs
from pathlib import Path

PORT = 8091
WWW_ROOT = Path(__file__).parent.parent

# In-memory storage
DATA = {
    'users': {},
    'sessions': {},
    'factions': {},
    'images': {},
    'requests': {}
}

def new_id(length=12):
    """Generate a random ID"""
    chars = 'abcdefghijklmnopqrstuvwxyz0123456789'
    return ''.join(secrets.choice(chars) for _ in range(length))

def hash_password(password, salt=None):
    """Hash a password"""
    if salt is None:
        salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
    return salt, h.hex()

def check_password(password, salt, hash_hex):
    """Check a password"""
    _, computed = hash_password(password, salt)
    return computed == hash_hex

def new_faction(owner, name, acronym):
    """Create a new faction"""
    fid = new_id()
    now = int(time.time())

    faction = {
        'id': fid,
        'owner': owner,
        'name': name,
        'acronym': acronym,
        'created': now,
        'updated': now,
        'current': 1,
        'maxVersion': 1,
        'versions': [{
            'n': 1,
            'from': None,
            'sections': [],
            'created': now,
            'deleted': False
        }],
        'session': {'n': 1, 'sections': [], 'last': now},
        'build': {
            'status': 'none',
            'liveVersion': None,
            'requestedAt': None,
            'builtAt': None,
            'history': []
        },
        'liveGameVersions': [],
        'design': new_design()
    }

    DATA['factions'][fid] = faction
    return faction

def new_design():
    """Create a new default design"""
    return {
        'meta': {'color': None},
        'card': {'image': None},
        'sbImages': {'mode': None, 'all': None, 'each': [None] * 6},
        'ae': {
            'enabled': False,
            'name': '',
            'acronym': '',
            'rows': [{'id': new_id(8), 'sign': '+', 'kind': 'fixed', 'qty': None, 'calc': '', 'desc': ''}]
        },
        'ufa': {
            'name': '', 'phase': None, 'type': None, 'hasCost': False, 'cost': None,
            'hasEffect': False, 'effect': None, 'text': ''
        },
        'setup': {
            'text': '', 'location': None, 'earthRegion': None, 'libraryRegion': None,
            'constraints': {
                'follows': None, 'water': True, 'land': True, 'emptyFactionGlyph': True,
                'thorn': True, 'dragon': True, 'chevron': True, 'noneOf3': True,
                'proximity': 'N/A', 'custom': ''
            },
            'gate': None,
            'units': [{'id': new_id(8), 'onMap': True, 'name': '', 'qty': None}],
            'power': 8,
            'aeStart': 0
        },
        'units': {'rows': []},
        'sbr': {
            'multiText': '',
            'rows': [{'id': new_id(8), 'text': '', 'hasNum': False, 'num': None} for _ in range(6)]
        },
        'sb': {
            'rows': [{'id': new_id(8), 'name': '', 'type': None, 'cost': 0, 'hasEffect': False, 'effect': None, 'text': ''} for _ in range(6)]
        },
        'region': {'rows': [{'id': new_id(8), 'name': '', 'image': None, 'restrictions': '', 'adjacency': ''}]},
        'tokens': {'rows': [{'id': new_id(8), 'name': '', 'qty': None, 'image': None, 'placement': '', 'effects': '', 'hasEffect': False, 'effect': None}]},
        'custom': {'rows': [{'id': new_id(8), 'name': '', 'image': None, 'placement': '', 'usage': '', 'effects': '', 'hasNum': False, 'num': None}]},
        'menus': {'rows': []}
    }

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WWW_ROOT), **kwargs)

    def do_GET(self):
        path = urlparse(self.path).path

        # API routes
        if path.startswith('/designer/api/'):
            self.handle_api_get(path)
        # Static files
        elif path == '/designer' or path == '/designer/':
            self.path = '/index.html'
            super().do_GET()
        elif path.startswith('/designer/'):
            self.path = path[len('/designer'):]
            super().do_GET()
        else:
            self.send_error(404)

    def do_POST(self):
        path = urlparse(self.path).path

        if path.startswith('/designer/api/'):
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length) if content_length > 0 else b''
            self.handle_api_post(path, body)
        else:
            self.send_error(404)

    def handle_api_get(self, path):
        """Handle GET API requests"""
        if path == '/designer/api/factions':
            token = self.headers.get('Authorization', '').replace('Bearer ', '')
            session = DATA['sessions'].get(token)
            if not session:
                self.send_json({'error': 'Unauthorized'}, 401)
                return

            user = session['user']
            factions = [
                {
                    'id': f['id'],
                    'name': f['name'],
                    'acronym': f['acronym'],
                    'current': f['current'],
                    'buildStatus': f['build']['status'],
                    'updated': f['updated']
                }
                for f in DATA['factions'].values()
                if f['owner'] == user
            ]
            self.send_json({'factions': factions})

        elif path.startswith('/designer/api/factions/') and '/requests' in path:
            fid = path.split('/')[4]
            self.send_json({'requests': []})

        elif path.startswith('/designer/api/factions/'):
            fid = path.split('/')[4]
            faction = DATA['factions'].get(fid)
            if not faction:
                self.send_json({'error': 'Faction not found'}, 404)
                return

            self.send_json({**faction, 'builtDesign': None})

        else:
            self.send_json({'error': 'Not found'}, 404)

    def handle_api_post(self, path, body):
        """Handle POST API requests"""
        try:
            data = json.loads(body) if body else {}
        except:
            data = {}

        if path == '/designer/api/register':
            username = data.get('username', '').lower()
            password = data.get('password', '')

            if username in DATA['users']:
                self.send_json({'error': 'Username already exists'}, 400)
                return

            salt, hash_hex = hash_password(password)
            token = secrets.token_urlsafe(32)

            DATA['users'][username] = {
                'username': username,
                'salt': salt,
                'hash': hash_hex,
                'created': int(time.time()),
                'lastLogin': int(time.time())
            }

            DATA['sessions'][token] = {
                'user': username,
                'expires': int(time.time()) + 2592000  # 30 days
            }

            self.send_json({'token': token, 'username': username})

        elif path == '/designer/api/login':
            username = data.get('username', '').lower()
            password = data.get('password', '')

            user = DATA['users'].get(username)
            if not user or not check_password(password, user['salt'], user['hash']):
                self.send_json({'error': 'Invalid username or password'}, 401)
                return

            token = secrets.token_urlsafe(32)
            DATA['sessions'][token] = {
                'user': username,
                'expires': int(time.time()) + 2592000
            }

            user['lastLogin'] = int(time.time())

            self.send_json({'token': token, 'username': username})

        elif path == '/designer/api/logout':
            token = self.headers.get('Authorization', '').replace('Bearer ', '')
            if token in DATA['sessions']:
                del DATA['sessions'][token]
            self.send_json({})

        elif path == '/designer/api/factions':
            token = self.headers.get('Authorization', '').replace('Bearer ', '')
            session = DATA['sessions'].get(token)
            if not session:
                self.send_json({'error': 'Unauthorized'}, 401)
                return

            name = data.get('name', '').strip()
            acronym = data.get('acronym', '').upper()

            if len(name) < 5:
                self.send_json({'error': 'Name must be at least 5 characters'}, 400)
                return

            faction = new_faction(session['user'], name, acronym)
            self.send_json({**faction, 'builtDesign': None})

        elif path.startswith('/designer/api/factions/') and path.endswith('/patch'):
            fid = path.split('/')[4]
            faction = DATA['factions'].get(fid)
            if not faction:
                self.send_json({'error': 'Faction not found'}, 404)
                return

            ops = data.get('ops', [])
            for op in ops:
                if op['op'] == 'set':
                    self.apply_set(faction['design'], op['path'], op['value'])

            faction['updated'] = int(time.time())

            self.send_json({
                'current': faction['current'],
                'maxVersion': faction['maxVersion'],
                'versions': faction['versions'],
                'session': faction['session'],
                'updated': faction['updated']
            })

        elif path.startswith('/designer/api/factions/') and path.endswith('/close-session'):
            self.send_json({})

        elif path.startswith('/designer/api/factions/') and path.endswith('/request'):
            self.send_json({'id': 'r_' + new_id(8), 'status': 'open'})

        elif path == '/designer/api/images':
            # Mock image upload
            image_id = hashlib.sha256(body).hexdigest()[:16] + '.webp'
            DATA['images'][image_id] = body
            self.send_json({'id': image_id, 'url': f'/designer/img/{image_id}'})

        else:
            self.send_json({'error': 'Not found'}, 404)

    def apply_set(self, obj, path, value):
        """Apply a set operation"""
        parts = path.split('.')
        for i, part in enumerate(parts[:-1]):
            if part.isdigit():
                obj = obj[int(part)]
            else:
                obj = obj[part]

        last = parts[-1]
        if last.isdigit():
            obj[int(last)] = value
        else:
            obj[last] = value

    def send_json(self, data, status=200):
        """Send a JSON response"""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, format, *args):
        """Suppress request logging except errors"""
        if args[1][0] not in '23':
            super().log_message(format, *args)

if __name__ == '__main__':
    with socketserver.TCPServer(('127.0.0.1', PORT), Handler) as httpd:
        print(f"Mock server running at http://127.0.0.1:{PORT}/designer/")
        print("Press Ctrl+C to stop")
        httpd.serve_forever()
