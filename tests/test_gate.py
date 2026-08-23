"""Fail/pass stories, hash-chain audit, shadow vs enforce CLI."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from framework.orchestrator import Orchestrator  # noqa: E402

FAIL = ROOT / "examples" / "checkov_fail.json"
PASS = ROOT / "examples" / "checkov_pass.json"
HOT = ROOT / "examples" / "telemetry_hot.json"
OK = ROOT / "examples" / "telemetry_ok.json"


def _run(checkov: Path, telemetry: Path, *, shadow: bool = True) -> dict:
    tmp = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
    tmp.close()
    orch = Orchestrator(Path(tmp.name))
    return orch.run(checkov, telemetry, shadow=shadow, service="checkout-api")


class GateStories(unittest.TestCase):
    def test_fail_story_blocks(self) -> None:
        result = _run(FAIL, HOT)
        self.assertIn("crc", result)
        self.assertIn("zeroguard", result)
        self.assertIn("infraagent", result)
        dsa = result["governance"]["decision"]["dsa"]
        self.assertEqual(dsa, "BLOCK")
        self.assertTrue(result["crc"]["residual_high"] or result["crc"]["critical_iac"])
        self.assertGreater(result["infraagent"]["phi_1h"], 0.7)

    def test_pass_story_allows(self) -> None:
        result = _run(PASS, OK)
        self.assertEqual(result["governance"]["decision"]["dsa"], "PASS")
        self.assertEqual(result["governance"]["decision"]["action"], "ALLOW")
        self.assertEqual(result["crc"]["eta"], 1.0)

    def test_open_sg_blocks_despite_healthy_traffic(self) -> None:
        result = _run(FAIL, OK)
        self.assertEqual(result["governance"]["decision"]["dsa"], "BLOCK")
        self.assertLess(result["infraagent"]["phi_1h"], 0.7)

    def test_hot_telemetry_blocks_despite_clean_iac(self) -> None:
        result = _run(PASS, HOT)
        self.assertEqual(result["governance"]["decision"]["dsa"], "BLOCK")
        self.assertFalse(result["crc"]["residual_high"])
        self.assertGreater(result["infraagent"]["phi_1h"], 0.7)

    def test_audit_chain_verifies(self) -> None:
        result = _run(FAIL, HOT)
        self.assertTrue(result["governance"]["audit"]["chain_ok"])
        kinds = {m["kind"] for m in result["governance"]["bus"]}
        self.assertGreaterEqual(
            kinds,
            {"RiskReport", "ZtaScore", "Forecast", "GateDecision", "Outcome"},
        )


class CliShadow(unittest.TestCase):
    def test_shadow_never_exit_2_on_block(self) -> None:
        proc = subprocess.run(
            [sys.executable, "-m", "framework.cli", str(FAIL), "--telemetry", str(HOT)],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["governance"]["decision"]["dsa"], "BLOCK")
        self.assertTrue(payload["governance"]["shadow"])

    def test_enforce_exit_2_on_block(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            audit = Path(td) / "audit.jsonl"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "framework.cli",
                    str(FAIL),
                    "--telemetry",
                    str(HOT),
                    "--enforce",
                    "--audit",
                    str(audit),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
        self.assertEqual(proc.returncode, 2, proc.stderr)

    def test_enforce_exit_0_on_allow(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            audit = Path(td) / "audit.jsonl"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "framework.cli",
                    str(PASS),
                    "--telemetry",
                    str(OK),
                    "--enforce",
                    "--audit",
                    str(audit),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
        self.assertEqual(proc.returncode, 0, proc.stderr)


if __name__ == "__main__":
    unittest.main()
