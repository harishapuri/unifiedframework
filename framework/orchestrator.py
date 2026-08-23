"""Decision fusion: ingest → CRC + ZeroGuard + InfraAgent on one bus → gate → audit.

Thin wrapper over `framework.flow.iter_flow` — the staged generator is the
single source of truth; this just runs it to completion and returns the
final `done` event's payload (used by the CLI and tests).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from framework.audit import AuditChain
from framework.bus import MessageBus
from framework.flow import iter_flow

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_AUDIT = ROOT / "data" / "audit.jsonl"


class Orchestrator:
    def __init__(self, audit_path: Path | None = None, bus_path: Path | None = None) -> None:
        dest = Path(audit_path) if audit_path else DEFAULT_AUDIT
        self.audit = AuditChain(dest)
        # Durable beside the audit file unless the caller asked for memory-only
        # by passing bus_path="" — tests that need isolation still pass a temp dir.
        if bus_path is None:
            bus_path = dest.with_name(dest.name + ".bus")
        self.bus = MessageBus(path=bus_path or None)

    def run(
        self,
        checkov_path: Path | str,
        telemetry_path: Path | str | None = None,
        *,
        autonomy: int = 2,
        shadow: bool = True,
        service: str = "unknown",
    ) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for event in iter_flow(
            checkov_path,
            telemetry_path,
            self.audit,
            autonomy=autonomy,
            shadow=shadow,
            service=service,
            bus=self.bus,
        ):
            if event["stage"] == "done":
                result = event["detail"]
        return result
