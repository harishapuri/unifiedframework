"""MAWS supervisor: allocate tasks to named agents, fuse on the bus, one DSA pick.

CRC runs first because η multiplies Ψ and Ω. Patches stay apply=false.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterator

from maws import agents

from framework.audit import AuditChain
from framework.bus import MessageBus

STAGES = ("ingest", "crc", "zeroguard", "infraagent", "gate", "audit", "done")

AGENTS = (
    "Supervisor",
    "IngestAgent",
    "CrcAgent",
    "ZeroGuardAgent",
    "InfraAgent",
    "DsaAgent",
    "RpaAgent",
    "AuditAgent",
)


def _event(
    stage: str,
    *,
    wait: float,
    detail: dict[str, Any],
    agent: str,
    task: str,
) -> dict[str, Any]:
    return {"stage": stage, "wait": wait, "detail": detail, "agent": agent, "task": task}


def iter_maws(
    checkov_path: Path | str,
    telemetry_path: Path | str | None,
    audit: AuditChain,
    *,
    autonomy: int = 2,
    shadow: bool = True,
    service: str = "unknown",
    bus: MessageBus | None = None,
) -> Iterator[dict[str, Any]]:
    bus = bus or MessageBus.from_env()

    yield _event(
        "ingest",
        wait=0.5,
        agent="IngestAgent",
        task="load_scan_and_traffic",
        detail={
            "checkov_source": str(checkov_path),
            "telemetry_source": str(telemetry_path) if telemetry_path else "defaults",
            "supervisor": "assign",
        },
    )

    checkov, telemetry = agents.ingest(checkov_path, telemetry_path)
    yield _event(
        "ingested",
        wait=0.5,
        agent="IngestAgent",
        task="loaded",
        detail={
            "n_passed": checkov["n_passed"],
            "n_failed": checkov["n_failed"],
            "telemetry": telemetry,
        },
    )

    crc = agents.score_crc(checkov)
    bus.publish("RiskReport", crc, priority="safety", source="CrcAgent", service=service)
    yield _event("crc", wait=0.9, agent="CrcAgent", task="score_rules", detail=crc)

    zeroguard = agents.score_zeroguard(
        checkov, telemetry, eta=crc["eta"], phi_bar=crc["phi_bar_debt"]
    )
    bus.publish("ZtaScore", zeroguard, priority="identity", source="ZeroGuardAgent", service=service)
    yield _event("zeroguard", wait=0.9, agent="ZeroGuardAgent", task="score_trust", detail=zeroguard)

    infraagent = agents.score_infra(telemetry, eta=crc["eta"])
    bus.publish("Forecast", infraagent, priority="capacity", source="InfraAgent", service=service)
    yield _event("infraagent", wait=0.9, agent="InfraAgent", task="score_stay_up", detail=infraagent)

    fused = {
        **crc,
        **zeroguard,
        **infraagent,
        "critical_iac": crc["critical_iac"] or zeroguard["critical_iac"],
    }
    decision = agents.decide_gate(fused, autonomy=autonomy)
    remediation = agents.suggest_rollout(decision, infraagent)
    compensation = agents.compensate(decision)
    bus.publish("GateDecision", decision, priority="safety", source="DsaAgent", service=service)
    bus.publish("PatchSet", remediation, priority="advisory", source="RpaAgent", service=service)
    yield _event(
        "gate",
        wait=1.0,
        agent="DsaAgent",
        task="decide",
        detail={**decision, "remediation": remediation, "compensation": compensation},
    )
    yield _event(
        "rpa",
        wait=0.35,
        agent="RpaAgent",
        task="suggest_only",
        detail=remediation,
    )
    yield _event(
        "compensate",
        wait=0.35,
        agent="Supervisor",
        task="stay_on_blue" if compensation["blue_stays_live"] else "allow_green",
        detail=compensation,
    )

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
            "maws": True,
            "compensation": compensation["policy"],
        },
        action=decision["action"],
        outcome=outcome,
        extra={
            "shadow": shadow,
            "autonomy": autonomy,
            "source": checkov["source"],
            "actual": "pending",
            "bus_backend": bus.backend,
            "orchestrator": "maws",
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
    yield _event("audit", wait=0.6, agent="AuditAgent", task="seal", detail=audit_detail)

    top_fails = [
        {
            "check_id": c["check_id"],
            "resource": c["resource"],
            "debt": c["debt"],
            "pillars": c["pillars"],
        }
        for c in sorted(checkov["failed"], key=lambda r: -r["debt"])[:8]
    ]

    yield _event(
        "done",
        wait=0.0,
        agent="Supervisor",
        task="complete",
        detail={
            "service": service,
            "crc": {**crc, "source": checkov["source"], "top_failed": top_fails},
            "zeroguard": zeroguard,
            "infraagent": infraagent,
            "governance": {
                "shadow": shadow,
                "decision": decision,
                "remediation": remediation,
                "compensation": compensation,
                "audit": audit_detail,
                "bus": bus.snapshot(),
                "bus_backend": bus.backend,
                "orchestrator": "maws",
            },
        },
    )
