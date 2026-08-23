"""Staged flow generator: new WARN/ROLLBACK dummy scenarios, stage ordering."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from framework.audit import AuditChain  # noqa: E402
from framework.flow import STAGES, iter_flow  # noqa: E402

PASS = ROOT / "examples" / "checkov_pass.json"
FAIL = ROOT / "examples" / "checkov_fail.json"
WARN_PHI6 = ROOT / "examples" / "telemetry_warn_phi6.json"
WARN_KAPPA = ROOT / "examples" / "telemetry_warn_kappa.json"
ROLLBACK_T = ROOT / "examples" / "telemetry_rollback.json"


def _events(checkov: Path, telemetry: Path) -> list[dict]:
    tmp = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
    tmp.close()
    audit = AuditChain(Path(tmp.name))
    return list(iter_flow(checkov, telemetry, audit, service="checkout-api"))


class StagedFlow(unittest.TestCase):
    def test_stage_order_matches_declared_stages(self) -> None:
        events = _events(PASS, WARN_PHI6)
        seen = [e["stage"] for e in events if e["stage"] != "ingested"]
        self.assertEqual(seen, list(STAGES))

    def test_every_event_has_wait_and_detail(self) -> None:
        for ev in _events(FAIL, WARN_KAPPA):
            self.assertIn("wait", ev)
            self.assertIn("detail", ev)
            self.assertGreaterEqual(float(ev["wait"]), 0.0)

    def test_final_done_event_matches_orchestrator_shape(self) -> None:
        events = _events(PASS, WARN_PHI6)
        done = events[-1]["detail"]
        self.assertEqual(set(done.keys()), {"service", "crc", "zeroguard", "infraagent", "governance"})


class DummyWarnAndRollbackScenarios(unittest.TestCase):
    def test_warn_via_phi6_not_phi1(self) -> None:
        events = _events(PASS, WARN_PHI6)
        decision = next(e["detail"] for e in events if e["stage"] == "gate")
        self.assertEqual(decision["dsa"], "WARN")
        self.assertEqual(decision["action"], "WARN")
        infra = next(e["detail"] for e in events if e["stage"] == "infraagent")
        self.assertLessEqual(infra["phi_1h"], 0.7)
        self.assertGreater(infra["phi_6h"], 0.5)

    def test_warn_via_capacity_kappa(self) -> None:
        events = _events(PASS, WARN_KAPPA)
        decision = next(e["detail"] for e in events if e["stage"] == "gate")
        self.assertEqual(decision["dsa"], "WARN")
        infra = next(e["detail"] for e in events if e["stage"] == "infraagent")
        self.assertGreater(infra["kappa"], 0.15)
        self.assertLessEqual(infra["phi_1h"], 0.7)
        self.assertLessEqual(infra["phi_6h"], 0.5)

    def test_rollback_on_severe_outage_with_clean_iac(self) -> None:
        events = _events(PASS, ROLLBACK_T)
        decision = next(e["detail"] for e in events if e["stage"] == "gate")
        self.assertEqual(decision["dsa"], "BLOCK")
        self.assertEqual(decision["action"], "ROLLBACK")
        crc = next(e["detail"] for e in events if e["stage"] == "crc")
        self.assertFalse(crc["residual_high"])


if __name__ == "__main__":
    unittest.main()
