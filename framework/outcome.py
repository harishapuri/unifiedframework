"""Sidecar log of what actually happened after a shadow/enforce pick.

The SHA-256 audit chain is immutable. Outcomes append next to it so you can
score false stops vs missed stops without rewriting history.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from framework.audit import AuditChain

ACTUALS = ("ok", "incident", "rollback", "brownout")
ROOT = Path(__file__).resolve().parent.parent
DEFAULT_AUDIT = ROOT / "data" / "audit.jsonl"
DEFAULT_OUTCOMES = ROOT / "data" / "outcomes.jsonl"

STOP_ACTIONS = {"BLOCK_BUILD", "BLOCK_DEPLOYMENT", "ROLLBACK"}


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text().splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def find_audit(audit: AuditChain, token: str) -> dict[str, Any] | None:
    token = token.lower()
    hits = [e for e in audit.entries if str(e.get("hash", "")).lower().startswith(token)]
    if len(hits) == 1:
        return hits[0]
    if not hits:
        return None
    raise ValueError(f"hash prefix {token!r} matches {len(hits)} audit rows; use more characters")


def record_outcome(
    audit_hash: str,
    actual: str,
    *,
    note: str = "",
    audit_path: Path | None = None,
    outcomes_path: Path | None = None,
) -> dict[str, Any]:
    actual = actual.lower().strip()
    if actual not in ACTUALS:
        raise ValueError(f"actual must be one of {ACTUALS}")
    audit = AuditChain(audit_path or DEFAULT_AUDIT)
    entry = find_audit(audit, audit_hash)
    if entry is None:
        raise ValueError(f"no audit row starts with {audit_hash!r}")
    row = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "audit_hash": entry["hash"],
        "audit_index": entry["index"],
        "predicted_action": entry["action"],
        "predicted_mode": entry["outcome"],
        "actual": actual,
        "note": note,
        "service": (entry.get("event") or "").split(":", 1)[-1],
    }
    path = outcomes_path or DEFAULT_OUTCOMES
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as handle:
        handle.write(json.dumps(row) + "\n")
    return row


def scorecard(
    *,
    audit_path: Path | None = None,
    outcomes_path: Path | None = None,
) -> dict[str, Any]:
    audit = AuditChain(audit_path or DEFAULT_AUDIT)
    outcomes = _load_jsonl(outcomes_path or DEFAULT_OUTCOMES)
    by_hash = {row["audit_hash"]: row for row in outcomes}
    labeled: list[dict[str, Any]] = []
    false_stop = 0
    missed_stop = 0
    correct_stop = 0
    correct_go = 0
    useful_wait = 0
    for entry in audit.entries:
        linked = by_hash.get(entry["hash"])
        if not linked:
            continue
        action = entry["action"]
        actual = linked["actual"]
        bucket = "other"
        if action in STOP_ACTIONS and actual == "ok":
            false_stop += 1
            bucket = "false_stop"
        elif action == "ALLOW" and actual in {"incident", "rollback", "brownout"}:
            missed_stop += 1
            bucket = "missed_stop"
        elif action in STOP_ACTIONS and actual in {"incident", "rollback", "brownout"}:
            correct_stop += 1
            bucket = "correct_stop"
        elif action == "ALLOW" and actual == "ok":
            correct_go += 1
            bucket = "correct_go"
        elif action == "WARN" and actual in {"incident", "rollback", "brownout"}:
            useful_wait += 1
            bucket = "useful_wait"
        elif action == "WARN" and actual == "ok":
            false_stop += 1
            bucket = "false_wait"
        labeled.append(
            {
                "hash": entry["hash"][:12],
                "action": action,
                "actual": actual,
                "bucket": bucket,
                "service": linked.get("service"),
            }
        )
    n = len(labeled)
    pending = len(audit.entries) - n
    return {
        "labeled": n,
        "pending_actual": pending,
        "false_stop": false_stop,
        "missed_stop": missed_stop,
        "correct_stop": correct_stop,
        "correct_go": correct_go,
        "useful_wait": useful_wait,
        "ready_for_enforce": n >= 8 and missed_stop == 0 and false_stop <= max(1, n // 10),
        "rows": labeled[-20:],
    }
