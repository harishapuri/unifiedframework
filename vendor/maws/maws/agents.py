"""Specialist agents. Each wraps one existing framework function. No extra math."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from framework.crc.eta import score as crc_score
from framework.infraagent.dsa import decide
from framework.infraagent.forecast import score as infra_score
from framework.infraagent.rpa import suggest as rpa_suggest
from framework.ingest.checkov import load_checkov
from framework.ingest.telemetry import load_telemetry
from framework.zeroguard.pillars import score as zg_score


def ingest(checkov_path: Path | str, telemetry_path: Path | str | None) -> tuple[dict[str, Any], dict[str, Any]]:
    return load_checkov(checkov_path), load_telemetry(telemetry_path)


def score_crc(checkov: dict[str, Any]) -> dict[str, Any]:
    return crc_score(checkov)


def score_zeroguard(checkov: dict[str, Any], telemetry: dict[str, Any], *, eta: float, phi_bar: float) -> dict[str, Any]:
    return zg_score(checkov, telemetry, eta=eta, phi_bar=phi_bar)


def score_infra(telemetry: dict[str, Any], *, eta: float) -> dict[str, Any]:
    return infra_score(telemetry, eta=eta)


def decide_gate(fused: dict[str, Any], *, autonomy: int) -> dict[str, Any]:
    return decide(fused, autonomy=autonomy)


def suggest_rollout(decision: dict[str, Any], infra: dict[str, Any]) -> dict[str, Any]:
    return rpa_suggest(decision, infra)


def compensate(decision: dict[str, Any]) -> dict[str, Any]:
    """Stay on blue unless the pick is go. Never auto-apply."""
    dsa = decision.get("dsa")
    if dsa == "PASS":
        return {
            "policy": "promote_green",
            "blue_stays_live": False,
            "apply": False,
            "text": "Gate says go. Customers may move to green.",
        }
    return {
        "policy": "stay_on_blue",
        "blue_stays_live": True,
        "apply": False,
        "text": "Keep customers on the old chatbot. Wait or stop.",
        "dsa": dsa,
    }
