"""New combined website: hub + completed-flow GIF + links to both demos.

    python3 -m hub
    http://127.0.0.1:8800
"""

from __future__ import annotations

import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

STATIC = Path(__file__).resolve().parent / "static"

MIME = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".gif": "image/gif",
    ".js": "application/javascript; charset=utf-8",
}


class HubHandler(BaseHTTPRequestHandler):
    server_version = "NorthstarHub/1.0"
    protocol_version = "HTTP/1.1"

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path in {"/", "/index.html"}:
            target = STATIC / "index.html"
        elif path.startswith("/assets/"):
            target = STATIC / path[len("/assets/") :]
        else:
            self.send_error(404, "not found")
            return
        if not target.is_file():
            self.send_error(404, "not found")
            return
        body = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", MIME.get(target.suffix, "application/octet-stream"))
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args) -> None:  # noqa: A002
        pass


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 8800), HubHandler)
    url = "http://127.0.0.1:8800/"
    print(f"Northstar hub running at {url}  (Ctrl+C to stop)")
    try:
        webbrowser.open(url)
    except Exception:
        pass
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
