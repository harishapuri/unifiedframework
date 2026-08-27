"""Copy a sealed audit row off the laptop into a folder or SIEM webhook."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen


def packet(result: dict[str, Any], actor: dict[str, Any]) -> dict[str, Any]:
    gov = result.get("governance") or {}
    audit = gov.get("audit") or {}
    decision = gov.get("decision") or {}
    return {
        "actor": actor.get("actor"),
        "actor_source": actor.get("source"),
        "service": result.get("service"),
        "shadow": gov.get("shadow"),
        "dsa": decision.get("dsa"),
        "action": decision.get("action"),
        "audit_hash": audit.get("hash"),
        "audit_index": audit.get("index"),
        "chain_ok": audit.get("chain_ok"),
        "apply": False,
    }


def _post(url: str, payload: dict[str, Any], token: str | None) -> dict[str, Any]:
    body = json.dumps(payload).encode()
    headers = {"Content-Type": "application/json", "User-Agent": "unified-gate/corp"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = Request(url, data=body, headers=headers, method="POST")
    try:
        with urlopen(req, timeout=8) as resp:  # noqa: S310
            return {"ok": True, "status": getattr(resp, "status", 200)}
    except URLError as exc:
        return {"ok": False, "error": str(exc.reason if hasattr(exc, "reason") else exc)}
    except OSError as exc:
        return {"ok": False, "error": str(exc)}


def export(
    result: dict[str, Any],
    actor: dict[str, Any],
    *,
    dest_dir: Path | str | None = None,
    webhook: str | None = None,
    token: str | None = None,
) -> dict[str, Any]:
    row = packet(result, actor)
    out: dict[str, Any] = {"packet": row, "file": None, "webhook": None}
    if dest_dir:
        path = Path(dest_dir)
        path.mkdir(parents=True, exist_ok=True)
        digest = str(row.get("audit_hash") or "row")[:16]
        target = path / f"evidence-{digest}.json"
        target.write_text(json.dumps(row, indent=2) + "\n")
        out["file"] = str(target)
    if webhook:
        out["webhook"] = _post(webhook, row, token)
    return out
