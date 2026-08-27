"""Map the fused pick to a blue/green *intent*. Never flips traffic itself.

A platform webhook (Argo / Istio / ALB) may consume this JSON. `apply` stays
false so a human or a separate CD job still owns the switch.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen


def intent_for(decision: dict[str, Any], *, service: str, actor: str) -> dict[str, Any]:
    dsa = str(decision.get("dsa") or "")
    action = str(decision.get("action") or "")
    if dsa == "BLOCK" or action in {"BLOCK_DEPLOYMENT", "ROLLBACK"}:
        command = "hold"
        green_weight = 0.0
        reason = "stay on blue"
    elif dsa == "WARN" or action == "WARN":
        command = "canary"
        green_weight = 0.1
        reason = "bake on 10% green"
    else:
        command = "promote"
        green_weight = 1.0
        reason = "gate says go"
    return {
        "apply": False,
        "suggest_only": True,
        "command": command,
        "green_weight": green_weight,
        "blue_stays_live": command != "promote",
        "service": service,
        "actor": actor,
        "dsa": dsa,
        "action": action,
        "reason": reason,
    }


def _post(url: str, payload: dict[str, Any], token: str | None) -> dict[str, Any]:
    body = json.dumps(payload).encode()
    headers = {"Content-Type": "application/json", "User-Agent": "unified-gate/corp"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = Request(url, data=body, headers=headers, method="POST")
    try:
        with urlopen(req, timeout=8) as resp:  # noqa: S310 — URL is operator-supplied
            return {"ok": True, "status": getattr(resp, "status", 200)}
    except URLError as exc:
        return {"ok": False, "error": str(exc.reason if hasattr(exc, "reason") else exc)}
    except OSError as exc:
        return {"ok": False, "error": str(exc)}


def emit(
    intent: dict[str, Any],
    *,
    dest_dir: Path | str | None = None,
    webhook: str | None = None,
    token: str | None = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {"intent": intent, "file": None, "webhook": None}
    if dest_dir:
        path = Path(dest_dir)
        path.mkdir(parents=True, exist_ok=True)
        target = path / "traffic_intent.json"
        target.write_text(json.dumps(intent, indent=2) + "\n")
        out["file"] = str(target)
    if webhook:
        posted = dict(intent)
        posted["apply"] = False
        out["webhook"] = _post(webhook, posted, token)
    return out
