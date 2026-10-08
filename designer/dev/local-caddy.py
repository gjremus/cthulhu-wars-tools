#!/usr/bin/env python3
"""Local stand-in for the live Caddy routes (dev only).

  /designer/          -> www/
  /designer/img/X     -> <data>/images/X
  /designer/api/*     -> proxied to the real designer_server.py on 127.0.0.1:<api-port>
  /admin.html         -> the Claude-Projects admin.html (admin API calls go to SERVER, so set it to this origin)

Usage: python3 dev/local-caddy.py --port 8095 --api-port 8091 --data /tmp/designer-e2e
"""
import argparse, http.server, os, urllib.request, urllib.error
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
ADMIN = HERE.parent / "admin" / "admin.html"


class H(http.server.BaseHTTPRequestHandler):
    def _proxy(self):
        n = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(n) if n else None
        hdrs = {k: v for k, v in self.headers.items() if k.lower() in ("content-type", "authorization")}
        req = urllib.request.Request(f"http://127.0.0.1:{A.api_port}{self.path}", data=body, headers=hdrs, method=self.command)
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                code, data, ct = r.status, r.read(), r.headers.get("Content-Type", "application/json")
        except urllib.error.HTTPError as e:
            code, data, ct = e.code, e.read(), e.headers.get("Content-Type", "application/json")
        self.send_response(code)
        self.send_header("Content-Type", ct)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _file(self, p):
        if not p.is_file():
            self.send_error(404)
            return
        data = p.read_bytes()
        ct = {".html": "text/html", ".js": "application/javascript", ".css": "text/css", ".json": "application/json",
              ".webp": "image/webp", ".png": "image/png", ".jpg": "image/jpeg", ".gif": "image/gif"}.get(p.suffix, "application/octet-stream")
        self.send_response(200)
        self.send_header("Content-Type", ct)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _route(self):
        path = self.path.split("?")[0]
        if path.startswith("/designer/api/"):
            return self._proxy()
        if path == "/designer":
            self.send_response(308); self.send_header("Location", "/designer/"); self.end_headers(); return
        if path.startswith("/designer/img/"):
            return self._file(Path(A.data) / "images" / os.path.basename(path))
        if path.startswith("/designer/"):
            rel = path[len("/designer/"):] or "index.html"
            p = (HERE / "www" / rel).resolve()
            if not str(p).startswith(str(HERE / "www")):
                return self.send_error(403)
            return self._file(p)
        if path.startswith("/HB/"):
            # Homebrew assets (fonts, unit art, map) come from the live server, as on production
            try:
                with urllib.request.urlopen("https://cwo.freeddns.org" + self.path, timeout=20) as r:
                    data, ct = r.read(), r.headers.get("Content-Type", "application/octet-stream")
                self.send_response(200); self.send_header("Content-Type", ct); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)
            except urllib.error.HTTPError as e:
                self.send_error(e.code)
            return
        if path == "/admin.html":
            return self._file(ADMIN)
        if path.startswith("/admin/"):
            # Stub game-server admin API so admin.html can sign in locally (one fake game, everything else empty)
            data = b"1\tTest Game\ttestslug\t0\t0\t0\t0\t1\t0\t0\tmain\n" if path.endswith("/games") else b""
            self.send_response(200); self.send_header("Content-Type", "text/plain"); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)
            return
        self.send_error(404)

    do_GET = do_POST = do_DELETE = _route

    def log_message(self, *a):
        pass


ap = argparse.ArgumentParser()
ap.add_argument("--port", type=int, default=8095)
ap.add_argument("--api-port", type=int, default=8091)
ap.add_argument("--data", required=True)
A = ap.parse_args()
http.server.ThreadingHTTPServer(("127.0.0.1", A.port), H).serve_forever()
