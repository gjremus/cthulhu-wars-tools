#!/usr/bin/env python3
"""
Mock admin API server for testing admin.html Custom Designs UI.
Stdlib only. Run: python3 mock-admin-api.py
Then open admin.html in a browser pointing to http://localhost:8092
"""

import http.server
import json
import socketserver
from urllib.parse import urlparse, parse_qs

PORT = 8092

# Mock data
MOCK_USERS = {
    "users": [
        {
            "username": "testuser1",
            "created": 1700000000,
            "lastLogin": 1700100000,
            "imageBytes": 1024000,
            "factions": [
                {
                    "id": "abc123xyz456",
                    "name": "Test Faction Alpha",
                    "acronym": "TFA",
                    "current": 3,
                    "buildStatus": "built",
                    "liveVersion": 2,
                    "updated": 1700100000
                },
                {
                    "id": "def456uvw789",
                    "name": "Beta Testers",
                    "acronym": "BET",
                    "current": 1,
                    "buildStatus": "requested",
                    "liveVersion": None,
                    "updated": 1700090000
                }
            ]
        },
        {
            "username": "designer2",
            "created": 1699000000,
            "lastLogin": 1700050000,
            "imageBytes": 512000,
            "factions": [
                {
                    "id": "ghi789rst012",
                    "name": "Gamma Squad",
                    "acronym": "GMS",
                    "current": 2,
                    "buildStatus": "none",
                    "liveVersion": None,
                    "updated": 1700080000
                }
            ]
        },
        {
            "username": "nofactions",
            "created": 1698000000,
            "lastLogin": 1699000000,
            "imageBytes": 0,
            "factions": []
        }
    ]
}

MOCK_REQUESTS = {
    "requests": [
        {
            "id": "r_abc123",
            "type": "build",
            "fid": "abc123xyz456",
            "faction": "Test Faction Alpha",
            "acronym": "TFA",
            "user": "testuser1",
            "status": "open",
            "created": 1700100000,
            "updated": 1700100000,
            "text": "Design complete and ready to execute build for Test Faction Alpha",
            "data": {"version": 3}
        },
        {
            "id": "r_def456",
            "type": "simple_update",
            "fid": "ghi789rst012",
            "faction": "Gamma Squad",
            "acronym": "GMS",
            "user": "designer2",
            "status": "notified",
            "created": 1700090000,
            "updated": 1700095000,
            "text": "Faction Gamma Squad update, change Units Cultist fixed value to 5",
            "data": {"section": "units", "rowId": "abc12345", "field": "qty", "name": "Cultist", "buildValue": 4, "designValue": 5}
        }
    ]
}


class MockHandler(http.server.SimpleHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path.startswith('/designer/api/admin/') and '/users' in path:
            self.send_json_response(MOCK_USERS)
        elif path.startswith('/designer/api/admin/') and '/requests' in path:
            # Parse status filter
            qs = parse_qs(parsed.query)
            status_filter = qs.get('status', [''])[0].split(',')
            filtered_requests = MOCK_REQUESTS["requests"]
            if status_filter and status_filter[0]:
                filtered_requests = [r for r in MOCK_REQUESTS["requests"] if r["status"] in status_filter]
            self.send_json_response({"requests": filtered_requests})
        else:
            self.send_response(404)
            self.send_header('Content-Type', 'text/plain')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(b'Not Found')

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path.endswith('/reset-password'):
            self.send_json_response({"ok": True})
        elif path.endswith('/delete'):
            self.send_json_response({"ok": True})
        else:
            self.send_response(404)
            self.send_header('Content-Type', 'text/plain')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(b'Not Found')

    def send_json_response(self, data):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)


if __name__ == '__main__':
    with socketserver.TCPServer(("", PORT), MockHandler) as httpd:
        print(f"Mock admin API server running on http://localhost:{PORT}")
        print("Test URL: http://localhost:8092/designer/api/admin/testtoken/users")
        httpd.serve_forever()
