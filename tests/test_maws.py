"""MAWS supervisor events on the unified flow."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from framework.audit import AuditChain  # noqa: E402
from framework.flow import iter_flow  # noqa: E402
from framework.locate_maws import locate  # noqa: E402

PASS = ROOT / "examples" / "checkov_pass.json"
FAIL = ROOT / "examples" / "checkov_fail.json"
OK = ROOT / "examples" / "telemetry_ok.json"
HOT = ROOT / "examples" / "telemetry_hot.json"


def _events(checkov: Path, telemetry: Path) -> list[dict]:
    tmp = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
    tmp.close()
    return list(iter_flow(checkov, telemetry, AuditChain(Path(tmp.name)), service="chatbot-api"))


class MawsHive(unittest.TestCase):
    def test_maws_package_is_located(self) -> None:
        self.assertIsNotNone(locate())

    def test_named_agents_on_core_stages(self) -> None:
        events = _events(PASS, OK)
        by_stage = {e["stage"]: e for e in events if "agent" in e}
        self.assertEqual(by_stage["crc"]["agent"], "CrcAgent")
        self.assertEqual(by_stage["zeroguard"]["agent"], "ZeroGuardAgent")
        self.assertEqual(by_stage["infraagent"]["agent"], "InfraAgent")
        self.assertEqual(by_stage["gate"]["agent"], "DsaAgent")
        self.assertEqual(by_stage["audit"]["agent"], "AuditAgent")

    def test_compensate_stay_on_blue_when_blocked(self) -> None:
        events = _events(FAIL, HOT)
        comp = next(e for e in events if e["stage"] == "compensate")
        self.assertTrue(comp["detail"]["blue_stays_live"])
        self.assertFalse(comp["detail"]["apply"])
        done = events[-1]["detail"]
        self.assertEqual(done["governance"]["orchestrator"], "maws")
        self.assertEqual(done["governance"]["decision"]["action"], "BLOCK_DEPLOYMENT")

    def test_pass_still_allow(self) -> None:
        events = _events(PASS, OK)
        decision = next(e["detail"] for e in events if e["stage"] == "gate")
        self.assertEqual(decision["action"], "ALLOW")
        bus = events[-1]["detail"]["governance"]["bus"]
        sources = {m["source"] for m in bus}
        self.assertIn("CrcAgent", sources)
        self.assertIn("DsaAgent", sources)
