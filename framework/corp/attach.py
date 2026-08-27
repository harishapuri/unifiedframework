"""Run corporate adapters after a fused pick. Gate math is already done."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from framework.corp.evidence import export
from framework.corp.identity import resolve_actor
from framework.corp.traffic import emit, intent_for


def attach(
    result: dict[str, Any],
    *,
    actor: str | None = None,
    export_evidence: Path | str | None = None,
    traffic_intent: Path | str | None = None,
    traffic_webhook: str | None = None,
    evidence_webhook: str | None = None,
) -> dict[str, Any]:
    who = resolve_actor(actor)
    gov = result.setdefault("governance", {})
    decision = gov.get("decision") or {}
    token = os.environ.get("GATE_TOKEN") or os.environ.get("EVIDENCE_WEBHOOK_TOKEN")
    intent = intent_for(decision, service=str(result.get("service") or ""), actor=who["actor"])
    traffic = emit(
        intent,
        dest_dir=traffic_intent,
        webhook=traffic_webhook or os.environ.get("TRAFFIC_WEBHOOK"),
        token=token,
    )
    evidence = export(
        result,
        who,
        dest_dir=export_evidence,
        webhook=evidence_webhook or os.environ.get("EVIDENCE_WEBHOOK"),
        token=token,
    )
    corp = {
        "actor": who,
        "traffic": traffic,
        "evidence": evidence,
        "apply": False,
        "enforce_unchanged": True,
    }
    gov["corp"] = corp
    result["governance"] = gov
    return result
