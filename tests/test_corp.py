"""Corporate adapters: scanners, traffic intent, evidence, actor. α2 unchanged."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Thread

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from framework.corp.attach import attach  # noqa: E402
from framework.corp.identity import resolve_actor  # noqa: E402
from framework.corp.traffic import intent_for  # noqa: E402
from framework.ingest.scanners import sarif_to_checkov, trivy_to_checkov, write_merged  # noqa: E402
from framework.orchestrator import Orchestrator  # noqa: E402

PASS = ROOT / "examples" / "checkov_pass.json"
FAIL = ROOT / "examples" / "checkov_fail.json"
OK = ROOT / "examples" / "telemetry_ok.json"
SARIF = ROOT / "examples" / "sarif_sample.json"
TRIVY = ROOT / "examples" / "trivy_sample.json"


class ScannerFold(unittest.TestCase):
    def test_sarif_failed_check(self) -> None:
        report = sarif_to_checkov(SARIF)
        self.assertEqual(report["summary"]["failed"], 1)
        self.assertEqual(report["results"]["failed_checks"][0]["check_id"], "SAST001")

    def test_trivy_failed_check(self) -> None:
        report = trivy_to_checkov(TRIVY)
        self.assertEqual(report["results"]["failed_checks"][0]["check_id"], "DS002")

    def test_merge_adds_failures_to_clean_checkov(self) -> None:
        dest = Path(tempfile.mkdtemp()) / "merged.json"
        write_merged(PASS, sarif=[SARIF], dest=dest)
        raw = json.loads(dest.read_text())
        self.assertGreaterEqual(raw["summary"]["failed"], 1)


class TrafficIntent(unittest.TestCase):
    def test_block_holds_green_and_never_applies(self) -> None:
        intent = intent_for({"dsa": "BLOCK", "action": "BLOCK_DEPLOYMENT"}, service="chat", actor="ci")
        self.assertEqual(intent["command"], "hold")
        self.assertEqual(intent["green_weight"], 0.0)
        self.assertFalse(intent["apply"])
        self.assertTrue(intent["blue_stays_live"])

    def test_pass_promotes_but_still_suggest_only(self) -> None:
        intent = intent_for({"dsa": "PASS", "action": "ALLOW"}, service="chat", actor="ci")
        self.assertEqual(intent["command"], "promote")
        self.assertFalse(intent["apply"])


class AttachCorp(unittest.TestCase):
    def test_actor_and_files(self) -> None:
        tmp = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
        tmp.close()
        result = Orchestrator(Path(tmp.name)).run(FAIL, OK, service="chatbot-api")
        ev = Path(tempfile.mkdtemp())
        tr = Path(tempfile.mkdtemp())
        os.environ["GATE_ACTOR"] = "release-bot"
        try:
            out = attach(result, export_evidence=ev, traffic_intent=tr)
        finally:
            os.environ.pop("GATE_ACTOR", None)
        self.assertEqual(out["governance"]["corp"]["actor"]["actor"], "release-bot")
        self.assertFalse(out["governance"]["corp"]["apply"])
        self.assertTrue((tr / "traffic_intent.json").is_file())
        self.assertTrue(list(ev.glob("evidence-*.json")))
        packet = json.loads(next(ev.glob("evidence-*.json")).read_text())
        self.assertEqual(packet["actor"], "release-bot")
        self.assertFalse(packet["apply"])

    def test_token_flag_never_echoed(self) -> None:
        os.environ["GATE_TOKEN"] = "super-secret"
        try:
            who = resolve_actor("alice")
        finally:
            os.environ.pop("GATE_TOKEN", None)
        self.assertTrue(who["token_configured"])
        self.assertNotIn("super-secret", json.dumps(who))


class Webhook(unittest.TestCase):
    def test_traffic_webhook_posts_apply_false(self) -> None:
        received: list[dict] = []

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802
                length = int(self.headers.get("Content-Length") or 0)
                received.append(json.loads(self.rfile.read(length)))
                self.send_response(204)
                self.end_headers()

            def log_message(self, fmt: str, *args) -> None:  # noqa: A002
                return

        server = HTTPServer(("127.0.0.1", 0), Handler)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        port = server.server_address[1]
        tmp = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
        tmp.close()
        result = Orchestrator(Path(tmp.name)).run(FAIL, OK, service="chatbot-api")
        try:
            attach(result, traffic_webhook=f"http://127.0.0.1:{port}/intent")
        finally:
            server.shutdown()
        self.assertEqual(len(received), 1)
        self.assertFalse(received[0]["apply"])
        self.assertEqual(received[0]["command"], "hold")


if __name__ == "__main__":
    unittest.main()
