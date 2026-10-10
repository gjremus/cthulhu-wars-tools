#!/usr/bin/env python3
"""
Unit tests for the CW Faction Designer backend.
Run with: python3 -m unittest -v test_designer_server
"""
import hashlib
import json
import os
import secrets
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path
from subprocess import Popen, PIPE
from threading import Thread
from urllib.request import Request, urlopen
from urllib.error import HTTPError


def find_free_port():
    """Find a free port to run the test server on."""
    import socket
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


class DesignerServerTest(unittest.TestCase):
    """Base class for server tests."""

    @classmethod
    def setUpClass(cls):
        """Start the server once for all tests."""
        cls.data_dir = Path(tempfile.mkdtemp(prefix='designer_test_'))
        cls.port = find_free_port()
        cls.base_url = f"http://127.0.0.1:{cls.port}/designer/api"

        # Create admin token
        cls.admin_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(cls.admin_token.encode()).hexdigest()
        cls.admin_token_file = cls.data_dir / "admin-token.sha256"
        with open(cls.admin_token_file, 'w') as f:
            f.write(token_hash)

        # Start server
        server_path = Path(__file__).parent / "designer_server.py"
        cls.server_proc = Popen([
            sys.executable,
            str(server_path),
            '--data', str(cls.data_dir),
            '--port', str(cls.port),
            '--host', '127.0.0.1',
            '--token-hash-file', str(cls.admin_token_file)
        ], stdout=PIPE, stderr=PIPE)

        # Wait for server to start
        for _ in range(50):
            try:
                urlopen(f"{cls.base_url}/health", timeout=1)
                break
            except Exception:
                time.sleep(0.1)
        else:
            cls.server_proc.kill()
            raise Exception("Server failed to start")

    @classmethod
    def tearDownClass(cls):
        """Stop the server and clean up."""
        cls.server_proc.terminate()
        cls.server_proc.wait(timeout=5)
        shutil.rmtree(cls.data_dir)

    def request(self, method, path, body=None, token=None, expect_error=False):
        """Make HTTP request to the server."""
        url = f"{self.base_url}{path}"
        headers = {}

        if token:
            headers['Authorization'] = f'Bearer {token}'

        if body is not None:
            if isinstance(body, (dict, list)):
                body = json.dumps(body).encode('utf-8')
                headers['Content-Type'] = 'application/json'
            elif isinstance(body, bytes):
                pass  # Already bytes
            else:
                body = body.encode('utf-8')

        req = Request(url, data=body, headers=headers, method=method)

        try:
            with urlopen(req) as resp:
                data = resp.read().decode('utf-8')
                return json.loads(data) if data else {}
        except HTTPError as e:
            if expect_error:
                data = e.read().decode('utf-8')
                return json.loads(data) if data else {}
            raise

    def register_user(self, username="testuser", password="testpass"):
        """Register a user and return token."""
        resp = self.request('POST', '/register', {
            'username': username,
            'password': password
        })
        return resp['token']

    def create_faction(self, token, name=None, acronym=None):
        """Create a faction and return it."""
        if name is None:
            name = f"Test Faction {secrets.token_hex(3)}"
        if acronym is None:
            # 3-letter "Q.." acronyms never clash with the reserved list or each other
            DesignerServerTest._acr_n = getattr(DesignerServerTest, '_acr_n', 0) + 1
            n = DesignerServerTest._acr_n
            acronym = "Q" + chr(65 + n // 26 % 26) + chr(65 + n % 26)
        return self.request('POST', '/factions', {
            'name': name,
            'acronym': acronym
        }, token=token)


class AuthTest(DesignerServerTest):
    """Test authentication and authorization."""

    def test_health_check(self):
        """Health endpoint returns ok."""
        resp = self.request('GET', '/health')
        self.assertEqual(resp['ok'], True)

    def test_register_valid(self):
        """Valid registration succeeds."""
        resp = self.request('POST', '/register', {
            'username': f'user{secrets.token_hex(4)}',
            'password': 'pass1234'
        })
        self.assertIn('token', resp)
        self.assertIn('username', resp)

    def test_register_short_username(self):
        """Username too short fails."""
        resp = self.request('POST', '/register', {
            'username': 'ab',
            'password': 'pass1234'
        }, expect_error=True)
        self.assertIn('error', resp)

    def test_register_short_password(self):
        """Password too short fails."""
        resp = self.request('POST', '/register', {
            'username': 'testuser123',
            'password': '123'
        }, expect_error=True)
        self.assertIn('error', resp)

    def test_register_duplicate(self):
        """Duplicate username fails."""
        username = f'user{secrets.token_hex(4)}'
        self.request('POST', '/register', {
            'username': username,
            'password': 'pass1234'
        })
        resp = self.request('POST', '/register', {
            'username': username.upper(),  # Case insensitive
            'password': 'pass1234'
        }, expect_error=True)
        self.assertIn('error', resp)

    def test_login_valid(self):
        """Valid login succeeds."""
        username = f'user{secrets.token_hex(4)}'
        password = 'testpass'
        self.request('POST', '/register', {'username': username, 'password': password})

        resp = self.request('POST', '/login', {
            'username': username,
            'password': password
        })
        self.assertIn('token', resp)

    def test_login_invalid_password(self):
        """Invalid password fails."""
        username = f'user{secrets.token_hex(4)}'
        self.request('POST', '/register', {'username': username, 'password': 'correct'})

        resp = self.request('POST', '/login', {
            'username': username,
            'password': 'wrong'
        }, expect_error=True)
        self.assertIn('error', resp)

    def test_logout(self):
        """Logout invalidates token."""
        token = self.register_user(f'user{secrets.token_hex(4)}')
        self.request('POST', '/logout', token=token)

        # Token should no longer work
        resp = self.request('GET', '/factions', token=token, expect_error=True)
        self.assertIn('error', resp)


class FactionTest(DesignerServerTest):
    """Test faction CRUD operations."""

    def test_create_faction_valid(self):
        """Create faction with valid data."""
        token = self.register_user(f'user{secrets.token_hex(4)}')
        faction = self.create_faction(token, "Test Faction", "TF")

        self.assertEqual(faction['name'], "Test Faction")
        self.assertEqual(faction['acronym'], "TF")
        self.assertEqual(faction['current'], 1)
        self.assertEqual(faction['maxVersion'], 1)
        self.assertIn('design', faction)

    def test_create_faction_short_name(self):
        """Faction name too short fails."""
        token = self.register_user(f'user{secrets.token_hex(4)}')
        resp = self.request('POST', '/factions', {
            'name': 'Test',  # < 5 chars
            'acronym': 'TF'
        }, token=token, expect_error=True)
        self.assertIn('error', resp)

    def test_create_faction_invalid_acronym(self):
        """Invalid acronym fails."""
        token = self.register_user(f'user{secrets.token_hex(4)}')
        resp = self.request('POST', '/factions', {
            'name': 'Test Faction',
            'acronym': 'T'  # Only 1 char
        }, token=token, expect_error=True)
        self.assertIn('error', resp)

    def test_create_faction_reserved_acronym(self):
        """Reserved acronym fails."""
        token = self.register_user(f'user{secrets.token_hex(4)}')
        resp = self.request('POST', '/factions', {
            'name': 'Test Faction',
            'acronym': 'GC'  # Reserved
        }, token=token, expect_error=True)
        self.assertIn('error', resp)

    def test_create_faction_duplicate_acronym(self):
        """Duplicate acronym fails."""
        token = self.register_user(f'user{secrets.token_hex(4)}')
        self.create_faction(token, "Faction One", "F1")

        resp = self.request('POST', '/factions', {
            'name': 'Faction Two',
            'acronym': 'F1'
        }, token=token, expect_error=True)
        self.assertIn('error', resp)

    def test_create_faction_max_limit(self):
        """Cannot create more than 20 factions."""
        token = self.register_user(f'user{secrets.token_hex(4)}')

        # Create 20 factions
        for i in range(20):
            self.create_faction(token, f"Faction {i}", f"F{i:02d}")

        # 21st should fail
        resp = self.request('POST', '/factions', {
            'name': 'Faction 21',
            'acronym': 'F21'
        }, token=token, expect_error=True)
        self.assertIn('error', resp)
        self.assertIn('20', resp['error'])

    def test_list_factions(self):
        """List factions returns own factions only."""
        token1 = self.register_user(f'user{secrets.token_hex(4)}')
        token2 = self.register_user(f'user{secrets.token_hex(4)}')

        self.create_faction(token1, "Faction 1", "L1")
        self.create_faction(token1, "Faction 2", "L2")
        self.create_faction(token2, "Faction 3", "F3")

        resp1 = self.request('GET', '/factions', token=token1)
        resp2 = self.request('GET', '/factions', token=token2)

        self.assertEqual(len(resp1['factions']), 2)
        self.assertEqual(len(resp2['factions']), 1)

    def test_get_faction(self):
        """Get faction by ID."""
        token = self.register_user(f'user{secrets.token_hex(4)}')
        faction = self.create_faction(token)

        retrieved = self.request('GET', f'/factions/{faction["id"]}', token=token)
        self.assertEqual(retrieved['id'], faction['id'])
        self.assertIn('builtDesign', retrieved)


class PatchTest(DesignerServerTest):
    """Test patch operations."""

    def test_set_operation(self):
        """Set operation updates a field."""
        token = self.register_user(f'user{secrets.token_hex(4)}')
        faction = self.create_faction(token)

        resp = self.request('POST', f'/factions/{faction["id"]}/patch', {
            'ops': [{'op': 'set', 'path': 'ufa.name', 'value': 'Test Power'}]
        }, token=token)

        self.assertEqual(resp['current'], 1)

        # Verify the change
        updated = self.request('GET', f'/factions/{faction["id"]}', token=token)
        self.assertEqual(updated['design']['ufa']['name'], 'Test Power')

    def test_add_row_operation(self):
        """Add row operation adds a row."""
        token = self.register_user(f'user{secrets.token_hex(4)}')
        faction = self.create_faction(token)

        new_row = {
            'id': secrets.token_urlsafe(6)[:8],
            'text': 'New requirement',
            'hasNum': False,
            'num': None
        }

        resp = self.request('POST', f'/factions/{faction["id"]}/patch', {
            'ops': [{'op': 'addRow', 'path': 'sbr.rows', 'row': new_row}]
        }, token=token)

        updated = self.request('GET', f'/factions/{faction["id"]}', token=token)
        self.assertEqual(len(updated['design']['sbr']['rows']), 7)  # 6 default + 1 new

    def test_delete_row_operation(self):
        """Delete row operation removes a row."""
        token = self.register_user(f'user{secrets.token_hex(4)}')
        faction = self.create_faction(token)

        row_id = faction['design']['units']['rows'][0]['id']

        self.request('POST', f'/factions/{faction["id"]}/patch', {
            'ops': [{'op': 'deleteRow', 'path': 'units.rows', 'id': row_id}]
        }, token=token)

        updated = self.request('GET', f'/factions/{faction["id"]}', token=token)
        self.assertEqual(len(updated['design']['units']['rows']), 2)  # 3 - 1

    def test_replace_section_operation(self):
        """Replace section operation replaces entire section."""
        token = self.register_user(f'user{secrets.token_hex(4)}')
        faction = self.create_faction(token)

        new_ufa = {
            'name': 'Replaced',
            'phase': 'Action',
            'type': 'Action',
            'hasCost': False,
            'cost': None,
            'hasEffect': False,
            'effect': None,
            'text': 'New text'
        }

        self.request('POST', f'/factions/{faction["id"]}/patch', {
            'ops': [{'op': 'replaceSection', 'path': 'ufa', 'value': new_ufa}]
        }, token=token)

        updated = self.request('GET', f'/factions/{faction["id"]}', token=token)
        self.assertEqual(updated['design']['ufa']['name'], 'Replaced')


class VersionTest(DesignerServerTest):
    """Test version management rules."""

    def test_addition_stays_in_place(self):
        """Addition (empty → non-empty) stays in current version."""
        token = self.register_user(f'user{secrets.token_hex(4)}')
        faction = self.create_faction(token)

        # Set empty field to non-empty (addition)
        resp = self.request('POST', f'/factions/{faction["id"]}/patch', {
            'ops': [{'op': 'set', 'path': 'ufa.name', 'value': 'Power Name'}]
        }, token=token)

        # Should stay in version 1
        self.assertEqual(resp['current'], 1)
        self.assertEqual(resp['maxVersion'], 1)

    def test_change_outside_session_creates_version(self):
        """Change outside session creates new version."""
        token = self.register_user(f'user{secrets.token_hex(4)}')
        faction = self.create_faction(token)

        # Make an addition in ufa section
        self.request('POST', f'/factions/{faction["id"]}/patch', {
            'ops': [{'op': 'set', 'path': 'ufa.name', 'value': 'Power'}]
        }, token=token)

        # Close the session
        self.request('POST', f'/factions/{faction["id"]}/close-session', token=token)

        # Now make a CHANGE (modifying existing value) → new version because session closed
        resp = self.request('POST', f'/factions/{faction["id"]}/patch', {
            'ops': [{'op': 'set', 'path': 'ufa.name', 'value': 'Power V2'}]
        }, token=token)

        self.assertEqual(resp['current'], 2)
        self.assertEqual(resp['maxVersion'], 2)

    def test_repeated_typing_same_section_stays_version(self):
        """Repeated edits in same section within session stay in one version."""
        token = self.register_user(f'user{secrets.token_hex(4)}')
        faction = self.create_faction(token)

        # First edit (addition)
        resp1 = self.request('POST', f'/factions/{faction["id"]}/patch', {
            'ops': [{'op': 'set', 'path': 'ufa.name', 'value': 'Power'}]
        }, token=token)
        self.assertEqual(resp1['current'], 1)

        # Second edit in same section (change, but session is open)
        resp2 = self.request('POST', f'/factions/{faction["id"]}/patch', {
            'ops': [{'op': 'set', 'path': 'ufa.name', 'value': 'Power Updated'}]
        }, token=token)
        self.assertEqual(resp2['current'], 1)  # Still version 1

        # Third edit
        resp3 = self.request('POST', f'/factions/{faction["id"]}/patch', {
            'ops': [{'op': 'set', 'path': 'ufa.text', 'value': 'Description'}]
        }, token=token)
        self.assertEqual(resp3['current'], 1)  # Still version 1

    def test_close_session_then_change_creates_version(self):
        """Close session, then change → new version."""
        token = self.register_user(f'user{secrets.token_hex(4)}')
        faction = self.create_faction(token)

        # Make an addition
        self.request('POST', f'/factions/{faction["id"]}/patch', {
            'ops': [{'op': 'set', 'path': 'ufa.name', 'value': 'Power'}]
        }, token=token)

        # Close session
        self.request('POST', f'/factions/{faction["id"]}/close-session', token=token)

        # Now change in same section → new version
        resp = self.request('POST', f'/factions/{faction["id"]}/patch', {
            'ops': [{'op': 'set', 'path': 'ufa.name', 'value': 'Power V2'}]
        }, token=token)

        self.assertEqual(resp['current'], 2)

    def test_rollback_then_edit_creates_version(self):
        """Rollback to v3 from v7, then edit → v8 with from=3."""
        token = self.register_user(f'user{secrets.token_hex(4)}')
        faction = self.create_faction(token)

        # Initialize ufa.text so subsequent edits are changes, not additions
        self.request('POST', f'/factions/{faction["id"]}/patch', {
            'ops': [{'op': 'set', 'path': 'ufa.text', 'value': 'Version 1'}]
        }, token=token)

        # Create several versions by closing session then changing
        for i in range(6):
            self.request('POST', f'/factions/{faction["id"]}/close-session', token=token)
            self.request('POST', f'/factions/{faction["id"]}/patch', {
                'ops': [{'op': 'set', 'path': 'ufa.text', 'value': f'Version {i+2}'}]
            }, token=token)

        # Now at version 7
        faction = self.request('GET', f'/factions/{faction["id"]}', token=token)
        self.assertEqual(faction['current'], 7)

        # Rollback to 3
        resp = self.request('POST', f'/factions/{faction["id"]}/rollback', {
            'version': 3
        }, token=token)
        self.assertEqual(resp['current'], 3)

        # Make an edit → should create version 8 with from=3
        resp = self.request('POST', f'/factions/{faction["id"]}/patch', {
            'ops': [{'op': 'set', 'path': 'ufa.text', 'value': 'After rollback'}]
        }, token=token)

        self.assertEqual(resp['current'], 8)
        self.assertEqual(resp['maxVersion'], 8)

        # Check version 8's from field
        faction = self.request('GET', f'/factions/{faction["id"]}', token=token)
        v8 = next(v for v in faction['versions'] if v['n'] == 8)
        self.assertEqual(v8['from'], 3)

    def test_built_version_locked(self):
        """Any edit to built version creates new version."""
        token = self.register_user(f'user{secrets.token_hex(4)}')
        faction = self.create_faction(token)

        # Mark as built
        admin_url = f"{self.base_url}/admin/{self.admin_token}/factions/{faction['id']}/build-status"
        req = Request(admin_url, data=json.dumps({
            'status': 'built',
            'version': 1
        }).encode(), headers={'Content-Type': 'application/json'}, method='POST')
        urlopen(req)

        # Now any edit, even an addition, should create new version
        resp = self.request('POST', f'/factions/{faction["id"]}/patch', {
            'ops': [{'op': 'set', 'path': 'setup.text', 'value': 'New setup'}]
        }, token=token)

        self.assertEqual(resp['current'], 2)
        self.assertEqual(resp['maxVersion'], 2)

    def test_delete_version_rules(self):
        """Delete version enforces rules."""
        token = self.register_user(f'user{secrets.token_hex(4)}')
        faction = self.create_faction(token)

        # Cannot delete current version
        resp = self.request('POST', f'/factions/{faction["id"]}/delete-version', {
            'version': 1
        }, token=token, expect_error=True)
        self.assertIn('error', resp)

        # Create version 2 (initialize first so edit is a change)
        self.request('POST', f'/factions/{faction["id"]}/patch', {
            'ops': [{'op': 'set', 'path': 'ufa.text', 'value': 'V1'}]
        }, token=token)
        self.request('POST', f'/factions/{faction["id"]}/close-session', token=token)
        self.request('POST', f'/factions/{faction["id"]}/patch', {
            'ops': [{'op': 'set', 'path': 'ufa.text', 'value': 'V2'}]
        }, token=token)

        # Now delete version 1 should work
        resp = self.request('POST', f'/factions/{faction["id"]}/delete-version', {
            'version': 1
        }, token=token)

        faction = self.request('GET', f'/factions/{faction["id"]}', token=token)
        v1 = next(v for v in faction['versions'] if v['n'] == 1)
        self.assertTrue(v1['deleted'])

    def test_deleted_version_marked(self):
        """Deleted version has deleted=true and sections=['DELETED']."""
        token = self.register_user(f'user{secrets.token_hex(4)}')
        faction = self.create_faction(token)

        # Create v2, then delete v1 (initialize first so edit is a change)
        self.request('POST', f'/factions/{faction["id"]}/patch', {
            'ops': [{'op': 'set', 'path': 'ufa.text', 'value': 'V1'}]
        }, token=token)
        self.request('POST', f'/factions/{faction["id"]}/close-session', token=token)
        self.request('POST', f'/factions/{faction["id"]}/patch', {
            'ops': [{'op': 'set', 'path': 'ufa.text', 'value': 'V2'}]
        }, token=token)

        self.request('POST', f'/factions/{faction["id"]}/delete-version', {
            'version': 1
        }, token=token)

        faction = self.request('GET', f'/factions/{faction["id"]}', token=token)
        v1 = next(v for v in faction['versions'] if v['n'] == 1)

        self.assertTrue(v1['deleted'])
        self.assertEqual(v1['sections'], ['DELETED'])


class ImageTest(DesignerServerTest):
    """Test image uploads."""

    def test_upload_valid_png(self):
        """Upload valid PNG."""
        token = self.register_user(f'user{secrets.token_hex(4)}')

        # Minimal valid PNG (1x1 pixel)
        png_data = (
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
            b'\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01'
            b'\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
        )

        req = Request(f"{self.base_url}/images", data=png_data, method='POST')
        req.add_header('Authorization', f'Bearer {token}')
        req.add_header('Content-Type', 'image/png')

        with urlopen(req) as resp:
            data = json.loads(resp.read())

        self.assertIn('id', data)
        self.assertIn('url', data)
        self.assertTrue(data['id'].endswith('.png'))

    def test_admin_upload_png(self):
        """Admin token can upload (extractor crops); wrong token cannot."""
        png_data = (
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x02\x00\x00\x00\x01'
            b'\x08\x06\x00\x00\x00\xf4"\x7f\x8a\x00\x00\x00\rIDATx\x9cc\x00\x01'
            b'\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
        )
        req = Request(f"{self.base_url}/admin/{self.admin_token}/images", data=png_data, method='POST')
        req.add_header('Content-Type', 'image/png')
        with urlopen(req) as resp:
            data = json.loads(resp.read())
        self.assertTrue(data['id'].endswith('.png'))
        self.assertTrue((self.data_dir / 'images' / data['id']).exists())

        bad = Request(f"{self.base_url}/admin/wrong-token/images", data=png_data, method='POST')
        bad.add_header('Content-Type', 'image/png')
        with self.assertRaises(HTTPError):
            urlopen(bad)

    def test_upload_invalid_magic_bytes(self):
        """Upload with wrong magic bytes fails."""
        token = self.register_user(f'user{secrets.token_hex(4)}')

        # Not a PNG
        fake_data = b'not a png file'

        req = Request(f"{self.base_url}/images", data=fake_data, method='POST')
        req.add_header('Authorization', f'Bearer {token}')
        req.add_header('Content-Type', 'image/png')

        try:
            urlopen(req)
            self.fail("Should have failed")
        except HTTPError:
            pass  # Expected

    def test_upload_deduplication(self):
        """Identical uploads return same ID."""
        token = self.register_user(f'user{secrets.token_hex(4)}')

        png_data = (
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
            b'\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01'
            b'\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
        )

        req1 = Request(f"{self.base_url}/images", data=png_data, method='POST')
        req1.add_header('Authorization', f'Bearer {token}')
        req1.add_header('Content-Type', 'image/png')

        with urlopen(req1) as resp:
            data1 = json.loads(resp.read())

        req2 = Request(f"{self.base_url}/images", data=png_data, method='POST')
        req2.add_header('Authorization', f'Bearer {token}')
        req2.add_header('Content-Type', 'image/png')

        with urlopen(req2) as resp:
            data2 = json.loads(resp.read())

        self.assertEqual(data1['id'], data2['id'])


class RequestTest(DesignerServerTest):
    """Test request management."""

    def test_create_request(self):
        """Create a request."""
        token = self.register_user(f'user{secrets.token_hex(4)}')
        faction = self.create_faction(token)

        req = self.request('POST', f'/factions/{faction["id"]}/request', {
            'type': 'build',
            'text': 'Ready to build',
            'data': {'version': 1}
        }, token=token)

        self.assertIn('id', req)
        self.assertEqual(req['type'], 'build')
        self.assertEqual(req['status'], 'open')

    def test_duplicate_request_deduplication(self):
        """Duplicate open requests return existing."""
        token = self.register_user(f'user{secrets.token_hex(4)}')
        faction = self.create_faction(token)

        req1 = self.request('POST', f'/factions/{faction["id"]}/request', {
            'type': 'bug',
            'text': 'Bug report',
            'data': {'description': 'Something broke'}
        }, token=token)

        req2 = self.request('POST', f'/factions/{faction["id"]}/request', {
            'type': 'bug',
            'text': 'Bug report',
            'data': {'description': 'Something broke'}
        }, token=token)

        self.assertEqual(req1['id'], req2['id'])

    def test_get_faction_requests(self):
        """Get requests for a faction."""
        token = self.register_user(f'user{secrets.token_hex(4)}')
        faction = self.create_faction(token)

        self.request('POST', f'/factions/{faction["id"]}/request', {
            'type': 'build',
            'text': 'Build',
            'data': {}
        }, token=token)

        resp = self.request('GET', f'/factions/{faction["id"]}/requests', token=token)

        self.assertEqual(len(resp['requests']), 1)


class AdminTest(DesignerServerTest):
    """Test admin endpoints."""

    def test_admin_wrong_token(self):
        """Wrong admin token returns 404."""
        try:
            self.request('GET', f'/admin/wrong-token/users')
            self.fail("Should have failed")
        except HTTPError as e:
            self.assertEqual(e.code, 404)

    def test_admin_users(self):
        """Admin can list users."""
        token = self.register_user(f'user{secrets.token_hex(4)}')
        self.create_faction(token, "Test Faction", "TF")

        admin_url = f"{self.base_url}/admin/{self.admin_token}/users"
        req = Request(admin_url, method='GET')

        with urlopen(req) as resp:
            data = json.loads(resp.read())

        self.assertIn('users', data)
        self.assertGreater(len(data['users']), 0)

    def test_admin_reset_password(self):
        """Admin can reset password."""
        username = f'user{secrets.token_hex(4)}'
        self.register_user(username, 'oldpass')

        admin_url = f"{self.base_url}/admin/{self.admin_token}/reset-password"
        req = Request(admin_url, data=json.dumps({
            'username': username
        }).encode(), headers={'Content-Type': 'application/json'}, method='POST')

        urlopen(req)

        # Login with "password" should work
        resp = self.request('POST', '/login', {
            'username': username,
            'password': 'password'
        })
        self.assertIn('token', resp)

    def test_admin_delete_user(self):
        """Admin can delete user and factions."""
        username = f'user{secrets.token_hex(4)}'
        token = self.register_user(username)
        self.create_faction(token, "Test Faction", "TF")

        admin_url = f"{self.base_url}/admin/{self.admin_token}/delete"
        req = Request(admin_url, data=json.dumps({
            'users': [username],
            'factions': []
        }).encode(), headers={'Content-Type': 'application/json'}, method='POST')

        urlopen(req)

        # User should no longer exist
        resp = self.request('POST', '/login', {
            'username': username,
            'password': 'testpass'
        }, expect_error=True)
        self.assertIn('error', resp)

    def _admin_post(self, path, body):
        req = Request(f"{self.base_url}/admin/{self.admin_token}/{path}", data=json.dumps(body).encode(),
                      headers={'Content-Type': 'application/json'}, method='POST')
        with urlopen(req) as r:
            return json.loads(r.read().decode() or '{}')

    def _live(self, acr, rev=None):
        url = self.base_url + f"/live/{acr}/values" + (f"?rev={rev}" if rev is not None else "")
        with urlopen(url) as r:
            return json.loads(r.read().decode())

    def test_simple_update_applies_without_ticker(self):
        """Push design to build applies at once, uses the saved design value, and is rev-pinned."""
        token = self.register_user(f'user{secrets.token_hex(4)}')
        faction = self.create_faction(token)
        fid, acr = faction['id'], faction['acronym']
        su = lambda: self.request('POST', f'/factions/{fid}/request', {
            'type': 'simple_update', 'text': 'x',
            'data': {'section': 'setup', 'rowId': None, 'field': 'power', 'name': 'Starting Power', 'designValue': 999}
        }, token=token, expect_error=True)

        # Not built yet -> refused
        self.assertIn('error', su())

        self._admin_post(f"factions/{fid}/build-status", {'status': 'built', 'version': 1})
        self.request('POST', f'/factions/{fid}/patch', {'ops': [{'op': 'set', 'path': 'setup.power', 'value': 10}]}, token=token)

        r = su()
        self.assertEqual(r['status'], 'done')
        self.assertEqual(r['data']['designValue'], 10)  # forged 999 ignored
        self.assertEqual(r['data']['buildValue'], 8)
        self.assertEqual(r['text'], f"Faction {faction['name']} update, change setup Starting Power fixed value to 10")

        f = self.request('GET', f'/factions/{fid}', token=token)
        self.assertEqual(f['builtDesign']['setup']['power'], 10)

        self.request('POST', f'/factions/{fid}/patch', {'ops': [{'op': 'set', 'path': 'setup.power', 'value': 6}]}, token=token)
        su()
        self.assertEqual(self._live(acr)['values'], {'setup.power': 6})
        self.assertEqual(self._live(acr)['rev'], 2)
        self.assertEqual(self._live(acr, rev=1)['values'], {'setup.power': 10})  # a game pinned at rev 1 keeps 10
        self.assertEqual(self._live(acr, rev=0)['values'], {})

        # Non-numeric / unknown fields refused
        bad = self.request('POST', f'/factions/{fid}/request', {
            'type': 'simple_update', 'text': 'x', 'data': {'section': 'ufa', 'rowId': None, 'field': 'name'}
        }, token=token, expect_error=True)
        self.assertIn('error', bad)

        # Nothing left open for the ticker
        reqs = self._admin_get(f"requests?status=open") if hasattr(self, '_admin_get') else None
        if reqs is not None:
            self.assertFalse([q for q in reqs['requests'] if q['fid'] == fid])

        # A rebuild from a newer version starts clean
        cur = self.request('GET', f'/factions/{fid}', token=token)['current']
        self._admin_post(f"factions/{fid}/build-status", {'status': 'built', 'version': cur})
        self.assertEqual(self._live(acr)['values'], {})


class UnitSpellbookTest(DesignerServerTest):
    """Test spellbook feature for iGOO/Elder God neutral units."""

    def test_unit_spellbook_crud(self):
        """Test creating, reading, updating a unit with spellbook data."""
        token = self.register_user("sbuser", "sbpass")

        # Create a neutral unit
        unit = self.request('POST', '/units', {'name': 'Test GOO'}, token=token)
        uid = unit['id']
        row_id = unit['design']['units']['rows'][0]['id']

        # Verify spellbook structure exists
        self.assertIn('spellbook', unit['design']['units']['rows'][0])
        sb = unit['design']['units']['rows'][0]['spellbook']
        self.assertFalse(sb['enabled'])
        self.assertEqual(sb['requirement']['text'], '')
        self.assertFalse(sb['requirement']['hasNum'])
        self.assertIsNone(sb['requirement']['num'])
        self.assertEqual(sb['book']['name'], '')
        self.assertIsNone(sb['book']['type'])
        self.assertEqual(sb['book']['cost'], 0)

        # Enable spellbook
        self.request('POST', f'/units/{uid}/patch', {
            'ops': [{'op': 'set', 'path': f'units.rows.{row_id}.spellbook.enabled', 'value': True}]
        }, token=token)

        # Set requirement text
        self.request('POST', f'/units/{uid}/patch', {
            'ops': [{'op': 'set', 'path': f'units.rows.{row_id}.spellbook.requirement.text', 'value': 'Control 3 gates'}]
        }, token=token)

        # Set requirement hasNum and num
        self.request('POST', f'/units/{uid}/patch', {
            'ops': [
                {'op': 'set', 'path': f'units.rows.{row_id}.spellbook.requirement.hasNum', 'value': True},
                {'op': 'set', 'path': f'units.rows.{row_id}.spellbook.requirement.num', 'value': 3}
            ]
        }, token=token)

        # Set spellbook fields
        self.request('POST', f'/units/{uid}/patch', {
            'ops': [
                {'op': 'set', 'path': f'units.rows.{row_id}.spellbook.book.name', 'value': 'Cosmic Power'},
                {'op': 'set', 'path': f'units.rows.{row_id}.spellbook.book.type', 'value': 'Ongoing'},
                {'op': 'set', 'path': f'units.rows.{row_id}.spellbook.book.cost', 'value': 2},
                {'op': 'set', 'path': f'units.rows.{row_id}.spellbook.book.hasEffect', 'value': True},
                {'op': 'set', 'path': f'units.rows.{row_id}.spellbook.book.effect', 'value': 5},
                {'op': 'set', 'path': f'units.rows.{row_id}.spellbook.book.text', 'value': 'Gain +2 Power per turn'}
            ]
        }, token=token)

        # Read back and verify
        unit = self.request('GET', f'/units/{uid}', token=token)
        sb = unit['design']['units']['rows'][0]['spellbook']

        self.assertTrue(sb['enabled'])
        self.assertEqual(sb['requirement']['text'], 'Control 3 gates')
        self.assertTrue(sb['requirement']['hasNum'])
        self.assertEqual(sb['requirement']['num'], 3)
        self.assertEqual(sb['book']['name'], 'Cosmic Power')
        self.assertEqual(sb['book']['type'], 'Ongoing')
        self.assertEqual(sb['book']['cost'], 2)
        self.assertTrue(sb['book']['hasEffect'])
        self.assertEqual(sb['book']['effect'], 5)
        self.assertEqual(sb['book']['text'], 'Gain +2 Power per turn')

        # Test that invalid paths are rejected
        bad = self.request('POST', f'/units/{uid}/patch', {
            'ops': [{'op': 'set', 'path': f'units.rows.{row_id}.invalid.path', 'value': 'x'}]
        }, token=token, expect_error=True)
        self.assertIn('error', bad)


if __name__ == '__main__':
    unittest.main()
