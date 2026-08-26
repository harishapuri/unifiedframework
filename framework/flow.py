"""Staged pipeline: MAWS supervisor when present, else the local fusion loop.

Callers (CLI, tests, SSE demos) always use `iter_flow`. The MAWS hive is the
orchestrator; scoring still lives in framework/crc, zeroguard, infraagent.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterator

from framework.audit import AuditChain
from framework.bus import MessageBus
from framework.crc.eta import score as crc_score
from framework.infraagent.dsa import decide
from framework.infraagent.forecast import score as infra_score
from framework.infraagent.rpa import suggest as rpa_suggest
from framework.ingest.checkov import load_checkov
from framework.ingest.telemetry import load_telemetry
from framework.locate_maws import iter_maws_or_none
from framework.zeroguard.pillars import score as zg_score

STAGES = ("ingest", "crc", "zeroguard", "infraagent", "gate", "audit", "done")


def iter_flow(
    checkov_path: Path | str,
    telemetry_path: Path | str | None,
    audit: AuditChain,
    *,
    autonomy: int = 2,
    shadow: bool = True,
    service: str = "unknown",
    bus: MessageBus | None = None,
) -> Iterator[dict[str, Any]]:
    maws = iter_maws_or_none(
        checkov_path,
        telemetry_path,
        audit,
        autonomy=autonomy,
        shadow=shadow,
        service=service,
        bus=bus,
    )
    if maws is not None:
        yield from maws
        return
    yield from _iter_flow_local(
        checkov_path,
        telemetry_path,
        audit,
        autonomy=autonomy,
        shadow=shadow,
        service=service,
        bus=bus,
    )


def _iter_flow_local(
    checkov_path: Path | str,
    telemetry_path: Path | str | None,
    audit: AuditChain,
    *,
    autonomy: int,
    shadow: bool,
    service: str,
    bus: MessageBus | None,
) -> Iterator[dict[str, Any]]:
    """Fallback if the MAWS package is not on disk (CI without vendor/maws)."""
    bus = bus or MessageBus.from_env()

    yield {
        "stage": "ingest",
        "wait": 0.5,
        "agent": "IngestAgent",
        "task": "load_scan_and_traffic",
        "detail": {
            "checkov_source": str(checkov_path),
            "telemetry_source": str(telemetry_path) if telemetry_path else "defaults",
        },
    }

    checkov = load_checkov(checkov_path)
    telemetry = load_telemetry(telemetry_path)
    yield {
        "stage": "ingested",
        "wait": 0.5,
        "agent": "IngestAgent",
        "task": "loaded",
        "detail": {
            "n_passed": checkov["n_passed"],
            "n_failed": checkov["n_failed"],
            "telemetry": telemetry,
        },
    }

    crc = crc_score(checkov)
    bus.publish("RiskReport", crc, priority="safety", source="CrcAgent", service=service)
    yield {"stage": "crc", "wait": 0.9, "agent": "CrcAgent", "task": "score_rules", "detail": crc}

    zeroguard = zg_score(checkov, telemetry, eta=crc["eta"], phi_bar=crc["phi_bar_debt"])
    bus.publish("ZtaScore", zeroguard, priority="identity", source="ZeroGuardAgent", service=service)
    yield {"stage": "zeroguard", "wait": 0.9, "agent": "ZeroGuardAgent", "task": "score_trust", "detail": zeroguard}

    infraagent = infra_score(telemetry, eta=crc["eta"])
    bus.publish("Forecast", infraagent, priority="capacity", source="InfraAgent", service=service)
    yield {"stage": "infraagent", "wait": 0.9, "agent": "InfraAgent", "task": "score_stay_up", "detail": infraagent}

    fused = {
        **crc,
        **zeroguard,
        **infraagent,
        "critical_iac": crc["critical_iac"] or zeroguard["critical_iac"],
    }
    decision = decide(fused, autonomy=autonomy)
    remediation = rpa_suggest(decision, infraagent)
    bus.publish("GateDecision", decision, priority="safety", source="DsaAgent", service=service)
    bus.publish("PatchSet", remediation, priority="advisory", source="RpaAgent", service=service)
    yield {"stage": "gate", "wait": 1.0, "agent": "DsaAgent", "task": "decide", "detail": {**decision, "remediation": remediation}}

    outcome = "shadow" if shadow else ("enforced" if decision["would_enforce"] else "advisory")
    entry = audit.append(
        event=f"deploy:{service}",
        traces={
            "eta": crc["eta"],
            "psi": zeroguard["psi"],
            "omega": infraagent["omega"],
            "phi_1h": infraagent["phi_1h"],
            "n_failed": crc["n_failed"],
            "reasons": decision["reasons"],
        },
        action=decision["action"],
        outcome=outcome,
        extra={
            "shadow": shadow,
            "autonomy": autonomy,
            "source": checkov["source"],
            "actual": "pending",
            "bus_backend": bus.backend,
        },
    )
    bus.publish(
        "Outcome",
        {"action": decision["action"], "outcome": outcome, "hash": entry["hash"]},
        priority="advisory",
        source="AuditAgent",
        service=service,
    )
    bus.drain()

    audit_detail = {
        "index": entry["index"],
        "hash": entry["hash"],
        "prev": entry["prev"][:12],
        "chain_ok": audit.verify(),
        "repaired": bool(getattr(audit, "repaired", False)),
    }
    yield {"stage": "audit", "wait": 0.6, "agent": "AuditAgent", "task": "seal", "detail": audit_detail}

    top_fails = [
        {
            "check_id": c["check_id"],
            "resource": c["resource"],
            "debt": c["debt"],
            "pillars": c["pillars"],
        }
        for c in sorted(checkov["failed"], key=lambda r: -r["debt"])[:8]
    ]

    yield {
        "stage": "done",
        "wait": 0.0,
        "agent": "Supervisor",
        "task": "complete",
        "detail": {
            "service": service,
            "crc": {**crc, "source": checkov["source"], "top_failed": top_fails},
            "zeroguard": zeroguard,
            "infraagent": infraagent,
            "governance": {
                "shadow": shadow,
                "decision": decision,
                "remediation": remediation,
                "audit": audit_detail,
                "bus": bus.snapshot(),
                "bus_backend": bus.backend,
            },
        },
    }
