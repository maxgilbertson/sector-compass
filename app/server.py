"""Sector Compass + World Compass: live global sector and country trackers.

Run:  py app/server.py   then open http://localhost:8765   (add --lan to reach it from phones on your Wi-Fi)
Prices come from Yahoo Finance's public chart API and are cached for
CACHE_SECONDS so open pages can poll without hammering it.
"""
import json
import sys
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import engine
import sectors
import world

PORT = next((int(a) for a in sys.argv[1:] if a.isdigit()), 8765)
CACHE_SECONDS = 300
HERE = Path(__file__).parent
PAGES = {"index.html", "world.html", "briefing.html", "common.css", "common.js"}  # the files the site is made of
BUILDS = {"data": sectors.build, "world": world.build}
TYPES = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8", ".js": "text/javascript; charset=utf-8",
         ".json": "application/json", ".md": "text/markdown; charset=utf-8"}

_cache = {name: {"at": 0, "body": None} for name in BUILDS}
_locks = {name: threading.Lock() for name in BUILDS}


def get_data(name="data", force=False):
    c = _cache[name]
    with _locks[name]:
        if force or not c["body"] or time.time() - c["at"] > CACHE_SECONDS:
            t0 = time.time()
            data = BUILDS[name]()
            data["buildSeconds"] = round(time.time() - t0, 1)
            c["body"] = json.dumps(engine.clean(data), separators=(",", ":"), allow_nan=False).encode()
            c["at"] = time.time()
            print(f"[{datetime.now():%H:%M:%S}] {name}: refreshed {len(data['rows'])} markets in "
                  f"{data['buildSeconds']}s; missing: {data['errors'] or 'none'}", flush=True)
        return c["body"]


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        u = urlparse(self.path)
        try:
            name = u.path.strip("/") or "index.html"
            if name.startswith("api/"):
                key = name[4:].removesuffix(".json")
                if key not in BUILDS:
                    return self._send(404, b"not found", "text/plain")
                self._send(200, get_data(key, force="force" in parse_qs(u.query)), "application/json")
            elif name in PAGES:
                self._send(200, (HERE / name).read_bytes(), TYPES[Path(name).suffix])
            elif name.startswith("briefings/") and ".." not in name and Path(name).suffix in (".json", ".md")                     and (HERE.parent / "data" / name).is_file():
                self._send(200, (HERE.parent / "data" / name).read_bytes(), TYPES[Path(name).suffix])
            else:
                self._send(404, b"not found", "text/plain")
        except Exception as e:  # noqa: BLE001
            self._send(500, json.dumps({"error": str(e)}).encode(), "application/json")

    def _send(self, code, body, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    if "--check" in sys.argv:
        for name in BUILDS:
            d = json.loads(get_data(name))
            print(name, "rows", len(d["rows"]), "errors", d["errors"])
        sys.exit()
    lan = "--lan" in sys.argv  # also serve other devices on the same Wi-Fi (e.g. your phone)
    print(f"Sector Compass running at http://localhost:{PORT}  (Ctrl+C to stop)", flush=True)
    if lan:
        import socket
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))  # no packets sent; just picks the Wi-Fi interface
                ip = s.getsockname()[0]
            print(f"\n  On your phone (same Wi-Fi), open:  http://{ip}:{PORT}\n", flush=True)
        except OSError:
            print("  Could not detect this PC's network address; run ipconfig to find it.", flush=True)
    for name in BUILDS:  # warm both caches
        threading.Thread(target=get_data, args=(name,), daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0" if lan else "127.0.0.1", PORT), Handler).serve_forever()
