"""Durable bus, exporter mapping, Holt CFA, outcome scorecard, suggest-only RPA."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from framework.bus import MessageBus  # noqa: E402
from framework.infraagent.forecast import holt_forecast, score as infra_score  # noqa: E402
from framework.ingest.telemetry import load_telemetry, normalize_telemetry  # noqa: E402
from framework.orchestrator import Orchestrator  # noqa: E402
from framework.outcome import record_outcome, scorecard  # noqa: E402

PASS = ROOT / "examples" / "checkov_pass.json"
FAIL = ROOT / "examples" / "checkov_fail.json"
OK = ROOT / "examples" / "telemetry_ok.json"
DATADOG = ROOT / "examples" / "telemetry_datadog.json"
HIST = ROOT / "examples" / "telemetry_history_hot.json"


class TelemetryMapping(unittest.TestCase):
    def test_datadog_series_maps_to_canonical_keys(self) -> None:
        tel = load_telemetry(DATADOG)
        self.assertAlmostEqual(tel["cpu"], 0.40, places=2)
        self.assertAlmostEqual(tel["error_rate"], 0.009, places=3)
        self.assertAlmostEqual(tel["latency_p95_ms"], 165.0, places=1)
        self.assertIn("history", tel)

    def test_prometheus_aliases(self) -> None:
        tel = normalize_telemetry(
            {
                "data": {
                    "result": [
                        {"metric": {"__name__": "http_error_rate"}, "value": [1, "0.02"]},
                        {"metric": {"__name__": "system_cpu_user"}, "value": [1, "0.33"]},
                    ]
                },
                "capacity": 1.0,
                "latency_p95_ms": 200,
            }
        )
        self.assertAlmostEqual(tel["error_rate"], 0.02)
        self.assertAlmostEqual(tel["cpu"], 0.33)


class HoltCapacity(unittest.TestCase):
    def test_rising_demand_forecasts_above_last_point(self) -> None:
        xs = [0.55, 0.72, 0.91, 1.08, 1.18, 1.30]
        self.assertGreater(holt_forecast(xs), xs[-1])

    def test_history_file_warns_on_capacity(self) -> None:
        tel = load_telemetry(HIST)
        scored = infra_score(tel, eta=1.0)
        self.assertEqual(scored["cfa_source"], "holt")
        self.assertGreater(scored["kappa"], 0.15)
        self.assertLessEqual(scored["phi_1h"], 0.7)

    def test_snapshot_examples_unchanged(self) -> None:
        tel = load_telemetry(OK)
        scored = infra_score(tel, eta=1.0)
        self.assertEqual(scored["cfa_source"], "snapshot")
        self.assertLess(scored["kappa"], 0.15)


class DurableBus(unittest.TestCase):
    def test_pending_survives_new_process_image(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "bus.jsonl"
            first = MessageBus(path=path)
            first.publish("Forecast", {"kappa": 0.2}, priority="capacity", source="cfa", service="chatbot-api")
            self.assertEqual(first.pending_count(), 1)
            revived = MessageBus(path=path)
            self.assertEqual(revived.backend, "file")
            self.assertEqual(revived.pending_count(), 1)
            drained = revived.drain()
            self.assertEqual(drained[0].kind, "Forecast")
            empty = MessageBus(path=path)
            self.assertEqual(empty.pending_count(), 0)
            self.assertEqual(empty.log[0].status, "consumed")


class OutcomeScorecard(unittest.TestCase):
    def test_record_and_score_without_rewriting_audit(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            audit = Path(td) / "audit.jsonl"
            outcomes = Path(td) / "outcomes.jsonl"
            orch = Orchestrator(audit)
            fail = orch.run(FAIL, ROOT / "examples" / "telemetry_hot.json", service="chatbot-api")
            allow = orch.run(PASS, OK, service="chatbot-api")
            self.assertTrue(orch.audit.verify())
            fail_hash = fail["governance"]["audit"]["hash"]
            allow_hash = allow["governance"]["audit"]["hash"]
            record_outcome(fail_hash, "incident", audit_path=audit, outcomes_path=outcomes, note="5xx on chatbot")
            record_outcome(allow_hash, "ok", audit_path=audit, outcomes_path=outcomes)
            card = scorecard(audit_path=audit, outcomes_path=outcomes)
            self.assertEqual(card["correct_stop"], 1)
            self.assertEqual(card["correct_go"], 1)
            self.assertEqual(card["missed_stop"], 0)
            self.assertTrue(orch.audit.verify())

    def test_remediation_is_suggest_only(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            orch = Orchestrator(Path(td) / "audit.jsonl")
            result = orch.run(FAIL, ROOT / "examples" / "telemetry_hot.json", service="chatbot-api")
            rem = result["governance"]["remediation"]
            self.assertTrue(rem["suggest_only"])
            self.assertFalse(rem["apply"])
            self.assertFalse(rem["proposals"][0]["apply"])


if __name__ == "__main__":
    unittest.main()
