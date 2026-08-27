"""Placeholder git_url is required; clone uses a local git repo in tests."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
import sys

sys.path.insert(0, str(ROOT))

from framework.ingest.git_scan import ScanTargetError, clone_and_scan, load_scan_target  # noqa: E402

FAIL = ROOT / "examples" / "checkov_fail.json"
PLACEHOLDER = ROOT / "examples" / "scan_target.placeholder.json"


class GitScan(unittest.TestCase):
    def test_placeholder_must_be_filled(self) -> None:
        with self.assertRaises(ScanTargetError):
            load_scan_target(PLACEHOLDER)

    def test_clone_local_repo(self) -> None:
        tmp = Path(tempfile.mkdtemp())
        repo = tmp / "src"
        repo.mkdir()
        (repo / "checkov.json").write_text(FAIL.read_text())
        subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-m", "f"],
            cwd=repo,
            check=True,
            capture_output=True,
        )
        target = tmp / "t.json"
        target.write_text(json.dumps({"git_url": str(repo), "ref": "main", "path": "."}))
        out, _ = clone_and_scan(load_scan_target(target), work_dir=tmp / "w")
        self.assertGreater(out.stat().st_size, 10)

    def test_parse_scan_target_rejects_placeholder(self) -> None:
        from framework.ingest.git_scan import parse_scan_target

        with self.assertRaises(ScanTargetError):
            parse_scan_target({"git_url": "REPLACE_WITH_GIT_REPO_URL"})


def _http_json(
    handler_cls,
    method: str,
    path: str,
    payload: dict | None = None,
    timeout: int = 30,
) -> tuple[int, dict]:
    import threading
    import urllib.error
    import urllib.request
    from http.server import ThreadingHTTPServer

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        data = None if payload is None or method == "GET" else json.dumps(payload).encode()
        headers = {"Content-Type": "application/json"} if data is not None else {}
        req = urllib.request.Request(
            f"http://127.0.0.1:{httpd.server_address[1]}{path}",
            data=data,
            headers=headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return int(resp.status), json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode()
            try:
                body = json.loads(raw)
            except json.JSONDecodeError:
                body = {"raw": raw}
            return int(exc.code), body
    finally:
        httpd.shutdown()
        httpd.server_close()


class AutomateHttpPost(unittest.TestCase):
    def test_webdemo_implements_do_post(self) -> None:
        from framework.webdemo import DemoHandler

        self.assertTrue(callable(getattr(DemoHandler, "do_POST", None)))

    def test_unfilled_placeholder_does_not_scan(self) -> None:
        from framework.demo_http import handle_automate, handle_scan

        status, body = handle_scan(
            {"git_url": "https://github.com/ORG/REPO.git"},
            audit=ROOT / "data" / "demo_audit.jsonl",
        )
        self.assertEqual(status, 400)
        self.assertIn("Fill the Git repo field", body["error"])

        status, body = handle_automate(
            {"git_url": "https://github.com/ORG/REPO.git"},
            run_fixtures=lambda: {"plane": "unified", "stories": [1], "passed": True},
            audit=ROOT / "data" / "demo_audit.jsonl",
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["source"], "fixtures")

    def test_post_scan_exists_never_501(self) -> None:
        from framework.webdemo import DemoHandler

        status, body = _http_json(
            DemoHandler,
            "POST",
            "/api/scan",
            {"git_url": "REPLACE_WITH_GIT_REPO_URL", "ref": "main", "path": "."},
        )
        self.assertNotEqual(status, 501, body)
        self.assertEqual(status, 400, body)
        self.assertIn("error", body)

    def test_post_scan_uncloneable_is_json_never_501(self) -> None:
        from framework.webdemo import DemoHandler

        status, body = _http_json(
            DemoHandler, "POST", "/api/scan", {"git_url": "/no/such/git/repo", "ref": "main", "path": "."}
        )
        self.assertNotEqual(status, 501, body)
        self.assertIn(status, (200, 400, 500), body)
        self.assertIsInstance(body, dict)
        self.assertIn("error", body)

    def test_get_automate_runs_fixtures(self) -> None:
        from framework.webdemo import DemoHandler

        status, body = _http_json(DemoHandler, "GET", "/api/automate", timeout=60)
        self.assertEqual(status, 200, body)
        self.assertEqual(body["source"], "fixtures")
        self.assertGreaterEqual(len(body.get("stories") or []), 7)
