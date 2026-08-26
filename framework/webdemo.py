"""Stdlib browser demo: click a story, watch CRC + ZeroGuard + InfraAgent fuse into one gate.

No new dependencies — `http.server` only. Run with:

    python3 -m framework.webdemo

Then open http://127.0.0.4:8877/
"""

from __future__ import annotations

import argparse
import json
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from framework.audit import AuditChain
from framework.bus import MessageBus
from framework.demo_http import apply_cors, resolve_static, send_options
from framework.flow import iter_flow
from framework.orchestrator import Orchestrator
from framework.peers import open_all_demo_pages, start_peer_demos

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "static"
EXAMPLES = ROOT / "examples"
DEMO_AUDIT = ROOT / "data" / "demo_audit.jsonl"
DEMO_BUS = DEMO_AUDIT.with_name(DEMO_AUDIT.name + ".bus")

# service, checkov fixture, telemetry fixture, one-line story for the UI.
STORIES: dict[str, tuple[Path, Path | None, str, str]] = {
    "pass": (
        EXAMPLES / "checkov_pass.json",
        EXAMPLES / "telemetry_ok.json",
        "chatbot-api",
        "The new chatbot looks safe and quiet. Send customers over.",
    ),
    "fail": (
        EXAMPLES / "checkov_fail.json",
        EXAMPLES / "telemetry_hot.json",
        "chatbot-api",
        "The network door is open and chat traffic looks attacked. Keep customers on the old chatbot.",
    ),
    "secure_but_hot": (
        EXAMPLES / "checkov_pass.json",
        EXAMPLES / "telemetry_hot.json",
        "chatbot-api",
        "The code is fine, but live traffic is about to fall over.",
    ),
    "open_sg_but_calm": (
        EXAMPLES / "checkov_fail.json",
        EXAMPLES / "telemetry_ok.json",
        "chatbot-api",
        "Traffic is calm, but the new chatbot’s network door is open.",
    ),
    "warn_rising_errors": (
        EXAMPLES / "checkov_pass.json",
        EXAMPLES / "telemetry_warn_phi6.json",
        "chatbot-api",
        "The code is fine, but trouble is likely in the next few hours.",
    ),
    "warn_capacity": (
        EXAMPLES / "checkov_pass.json",
        EXAMPLES / "telemetry_warn_kappa.json",
        "chatbot-api",
        "The code is fine, but we are about to run out of room.",
    ),
    "rollback": (
        EXAMPLES / "checkov_pass.json",
        EXAMPLES / "telemetry_rollback.json",
        "chatbot-api",
        "The code is fine, but the live site is already down. Undo.",
    ),
}

STORY_ORDER = ["pass", "warn_capacity", "warn_rising_errors", "fail", "secure_but_hot", "open_sg_but_calm", "rollback"]

MIME = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
}


class DemoHandler(BaseHTTPRequestHandler):
    server_version = "UnifiedFrameworkDemo/1.0"
    protocol_version = "HTTP/1.1"

    def _send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        apply_cors(self)
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path) -> None:
        if not path.is_file():
            self.send_error(404, "not found")
            return
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", MIME.get(path.suffix, "application/octet-stream"))
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store, max-age=0")
        apply_cors(self)
        self.end_headers()
        self.wfile.write(body)

    def _sse_write(self, event: dict) -> None:
        chunk = f"data: {json.dumps(event)}\n\n".encode()
        self.wfile.write(chunk)
        self.wfile.flush()

    def _stream_stories(self, story_keys: list[str]) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        apply_cors(self)
        self.end_headers()
        audit = AuditChain(DEMO_AUDIT)
        bus = MessageBus(path=DEMO_BUS)
        try:
            for story in story_keys:
                checkov_path, telemetry_path, service, blurb = STORIES[story]
                self._sse_write(
                    {
                        "stage": "scenario_start",
                        "wait": 0.4,
                        "story": story,
                        "detail": {"blurb": blurb, "service": service},
                    }
                )
                time.sleep(0.4)
                for ev in iter_flow(
                    checkov_path,
                    telemetry_path,
                    audit,
                    service=service,
                    shadow=True,
                    bus=bus,
                ):
                    ev["story"] = story
                    self._sse_write(ev)
                    time.sleep(float(ev.get("wait", 0.4)))
            self._sse_write({"stage": "stream_done", "wait": 0.0, "detail": {}})
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_OPTIONS(self) -> None:  # noqa: N802
        send_options(self)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        static = resolve_static(STATIC, parsed.path)
        if static is not None:
            self._send_file(static)
            return
        if parsed.path == "/api/stories":
            self._send_json(
                {
                    "order": STORY_ORDER,
                    "blurbs": {k: v[3] for k, v in STORIES.items()},
                }
            )
            return
        if parsed.path == "/api/run":
            qs = parse_qs(parsed.query)
            story = (qs.get("story") or ["pass"])[0]
            if story not in STORIES:
                self._send_json({"error": f"unknown story '{story}'"}, status=400)
                return
            checkov_path, telemetry_path, service, _ = STORIES[story]
            orch = Orchestrator(DEMO_AUDIT)
            result = orch.run(checkov_path, telemetry_path, service=service, shadow=True)
            result["story"] = story
            self._send_json(result)
            return
        if parsed.path == "/api/stream":
            qs = parse_qs(parsed.query)
            story = (qs.get("story") or ["pass"])[0]
            if story == "all":
                self._stream_stories(STORY_ORDER)
            elif story in STORIES:
                self._stream_stories([story])
            else:
                self._send_json({"error": f"unknown story '{story}'"}, status=400)
            return
        self.send_error(404, "not found")

    def log_message(self, fmt: str, *args) -> None:  # noqa: A002 - silence default access log
        pass


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Unified framework demo")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--no-peers", action="store_true")
    args = parser.parse_args(argv)
    DEMO_AUDIT.parent.mkdir(parents=True, exist_ok=True)
    if not args.no_peers:
        started = start_peer_demos(desktop=ROOT.parent, self_port=8877)
        if started:
            print("also started " + ", ".join(started), flush=True)
    server = ThreadingHTTPServer(("127.0.0.1", 8877), DemoHandler)
    url = "http://127.0.0.1:8877/"
    print(f"Unified framework demo running at {url}  (Ctrl+C to stop)", flush=True)
    print("Sites (one project each):", flush=True)
    print("  CICD      http://127.0.0.1:8871/", flush=True)
    print("  Infra     http://127.0.0.1:8872/", flush=True)
    print("  ZeroGuard http://127.0.0.1:8873/", flush=True)
    print("  MAWS      http://127.0.0.1:8874/", flush=True)
    print("  Unified   http://127.0.0.1:8877/", flush=True)
    if not args.no_browser:
        open_all_demo_pages()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
