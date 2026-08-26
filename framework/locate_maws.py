"""Put the MAWS package on sys.path (env, sibling checkout, then vendored copy)."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Iterator

from framework.audit import AuditChain
from framework.bus import MessageBus

UNIFIED_ROOT = Path(__file__).resolve().parent.parent


def _candidates() -> list[Path]:
    env = os.environ.get("MAWS_ROOT")
    paths: list[Path] = []
    if env:
        paths.append(Path(env).expanduser().resolve())
    paths.append(UNIFIED_ROOT.parent / "maws")
    paths.append(UNIFIED_ROOT.parent.parent)
    paths.append(UNIFIED_ROOT / "vendor" / "maws")
    return paths


def locate() -> Path | None:
    for path in _candidates():
        if (path / "maws" / "supervisor.py").is_file():
            resolved = str(path)
            if resolved not in sys.path:
                sys.path.insert(0, resolved)
            return path
    return None


def iter_maws_or_none(
    checkov_path: Path | str,
    telemetry_path: Path | str | None,
    audit: AuditChain,
    *,
    autonomy: int,
    shadow: bool,
    service: str,
    bus: MessageBus | None,
) -> Iterator[dict[str, Any]] | None:
    if locate() is None:
        return None
    from maws.supervisor import iter_maws

    return iter_maws(
        checkov_path,
        telemetry_path,
        audit,
        autonomy=autonomy,
        shadow=shadow,
        service=service,
        bus=bus,
    )
