"""Preview the built site exactly as GitHub Pages will serve it, under the project base path.

    python site/serve.py                 # builds the site, then serves http://localhost:8765/credit-model-stress-testing/
    python site/serve.py --no-build      # serve the existing site/dist
    python site/serve.py --port 9000

Anything outside the base path returns 404, as it would on Pages. Standard library only.
"""

from __future__ import annotations

import argparse
import gzip
import json
import os
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SITE = Path(__file__).resolve().parent
DIST = SITE / "dist"


class Handler(SimpleHTTPRequestHandler):
    base = "/"

    def translate_path(self, path: str) -> str:
        path = path.split("?", 1)[0].split("#", 1)[0]
        if not path.startswith(self.base):
            return str(DIST / "__not_found__")
        return super().translate_path("/" + path[len(self.base):])

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self.send_response(302)
            self.send_header("Location", self.base)
            self.end_headers()
            return
        # Pages gzips text files, so do the same here to get realistic load times.
        local = self.translate_path(self.path)
        if os.path.isdir(local):
            local = os.path.join(local, "index.html")
        ext = os.path.splitext(local)[1]
        if ext in (".html", ".css", ".js", ".json") and os.path.isfile(local) and "gzip" in self.headers.get("Accept-Encoding", ""):
            body = gzip.compress(Path(local).read_bytes(), 6)
            self.send_response(200)
            self.send_header("Content-Type", self.extensions_map.get(ext, "text/html") + ("; charset=utf-8" if ext in (".html", ".css", ".js", ".json") else ""))
            self.send_header("Content-Encoding", "gzip")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt, *args):
        sys.stderr.write("%s %s\n" % (self.address_string(), fmt % args))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-build", action="store_true")
    args = ap.parse_args()
    if not args.no_build:
        sys.path.insert(0, str(SITE))
        import build_site  # noqa: PLC0415

        build_site.build()
    base = os.environ.get("SITE_BASE_PATH") or json.loads((SITE / "config.json").read_text(encoding="utf-8"))["base_path"]
    Handler.base = base
    Handler.extensions_map = {**Handler.extensions_map, ".js": "text/javascript", ".json": "application/json", ".css": "text/css", ".html": "text/html"}
    server = ThreadingHTTPServer(("127.0.0.1", args.port), partial(Handler, directory=str(DIST)))
    print(f"Serving {DIST}\nOpen http://localhost:{args.port}{base}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
