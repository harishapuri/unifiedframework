"""Demo stories for the MAWS hive (same fused picks as the other planes)."""

from __future__ import annotations

from pathlib import Path

from maws.bootstrap import ROOT, UNIFIED_ROOT

EXAMPLES = UNIFIED_ROOT / "examples"
STATIC = ROOT / "demo" / "static"
DEMO_AUDIT = ROOT / "data" / "demo_audit.jsonl"
PORT = 8874
HOST = "127.0.0.1"
SITE = f"http://{HOST}:{PORT}"
TITLE = "MAWS — supervisor hive demo"
KICKER = "MAWS · orchestrator"

STORIES: dict[str, tuple[Path, Path, str, str]] = {
    "pass": (
        EXAMPLES / "checkov_pass.json",
        EXAMPLES / "telemetry_ok.json",
        "chatbot-api",
        "Supervisor assigns agents. If all three planes agree, go.",
    ),
    "fail": (
        EXAMPLES / "checkov_fail.json",
        EXAMPLES / "telemetry_hot.json",
        "chatbot-api",
        "Hive still stops: open door plus hot traffic. Stay on blue.",
    ),
    "secure_but_hot": (
        EXAMPLES / "checkov_pass.json",
        EXAMPLES / "telemetry_hot.json",
        "chatbot-api",
        "Rules passed. Stay-up agent still undoes. Compensation: stay on blue.",
    ),
    "open_sg_but_calm": (
        EXAMPLES / "checkov_fail.json",
        EXAMPLES / "telemetry_ok.json",
        "chatbot-api",
        "Calm traffic. Trust/rules agents still stop. Stay on blue.",
    ),
    "warn_rising_errors": (
        EXAMPLES / "checkov_pass.json",
        EXAMPLES / "telemetry_warn_phi6.json",
        "chatbot-api",
        "Supervisor waits: trouble likely in a few hours.",
    ),
    "warn_capacity": (
        EXAMPLES / "checkov_pass.json",
        EXAMPLES / "telemetry_warn_kappa.json",
        "chatbot-api",
        "Supervisor waits: about to run out of room.",
    ),
    "rollback": (
        EXAMPLES / "checkov_pass.json",
        EXAMPLES / "telemetry_rollback.json",
        "chatbot-api",
        "Live site is down. Compensation: undo, stay on blue.",
    ),
}

STORY_ORDER = [
    "pass",
    "warn_capacity",
    "warn_rising_errors",
    "fail",
    "secure_but_hot",
    "open_sg_but_calm",
    "rollback",
]

EXPECTED = {
    "pass": ("PASS", "ALLOW"),
    "fail": ("BLOCK", "BLOCK_DEPLOYMENT"),
    "secure_but_hot": ("BLOCK", "ROLLBACK"),
    "open_sg_but_calm": ("BLOCK", "BLOCK_DEPLOYMENT"),
    "warn_rising_errors": ("WARN", "WARN"),
    "warn_capacity": ("WARN", "WARN"),
    "rollback": ("BLOCK", "ROLLBACK"),
}
