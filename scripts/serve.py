#!/usr/bin/env python3
"""Serve dist/ on loopback for a local look.  [LAPTOP]

    python3 scripts/serve.py [port]        default 8791

Loopback only: this is a preview, not a way to publish. Sends the same
headers the host will send, so what you see is what a visitor gets.
"""
import http.server
import json
import sys
from functools import partial
from pathlib import Path

DIST = Path(__file__).resolve().parents[1] / "dist"
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8791


class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map,
                      ".webp": "image/webp", ".woff2": "font/woff2", ".svg": "image/svg+xml"}

    def end_headers(self):
        for h in HEADERS:
            self.send_header(h["key"], h["value"])
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt, *args):
        sys.stdout.write("%s %s\n" % (self.address_string(), fmt % args)); sys.stdout.flush()


if not (DIST / "index.html").is_file():
    sys.exit("serve: dist/index.html missing — run: bash scripts/build.sh")
HEADERS = json.loads((DIST / "vercel.json").read_text())["headers"][0]["headers"]
http.server.ThreadingHTTPServer.allow_reuse_address = True
with http.server.ThreadingHTTPServer(("127.0.0.1", PORT), partial(Handler, directory=str(DIST))) as srv:
    print(f"serve: http://127.0.0.1:{PORT}/  (Ctrl-C to stop)"); sys.stdout.flush()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
