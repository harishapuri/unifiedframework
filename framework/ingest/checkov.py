"""Ingest Checkov JSON (`checkov -o json`) into failed/passed check records."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from framework.zeroguard.pillars import classify_check, severity_weight


def _iter_reports(raw: Any) -> list[dict[str, Any]]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, dict)]
    if isinstance(raw, dict):
        if "results" in raw or "summary" in raw:
            return [raw]
        out = []
        for v in raw.values():
            if isinstance(v, dict) and "results" in v:
                out.append(v)
            elif isinstance(v, list):
                out.extend(_iter_reports(v))
        return out or [raw]
    return []


def _checks(block: dict[str, Any], key: str) -> list[dict[str, Any]]:
    results = block.get("results") or {}
    rows = results.get(key) or []
    return [c for c in rows if isinstance(c, dict)]


def _normalize(c: dict[str, Any], passed_ok: bool) -> dict[str, Any]:
    cid = str(c.get("check_id") or c.get("id") or "")
    name = str(c.get("check_name") or c.get("name") or "")
    guideline = str(c.get("guideline") or "")
    pillars, debt = classify_check(cid, name, guideline)
    sev = c.get("severity")
    if isinstance(sev, dict):
        sev = sev.get("level") or sev.get("name")
    weight = max(debt, severity_weight(str(sev) if sev else None))
    if passed_ok:
        weight = 0
    return {
        "check_id": cid,
        "check_name": name,
        "resource": c.get("resource") or c.get("resource_address") or "",
        "file_path": c.get("file_path") or c.get("file_abs_path") or "",
        "severity": sev,
        "pillars": list(pillars),
        "debt": weight,
        "passed": passed_ok,
    }


def load_checkov(path: Path | str) -> dict[str, Any]:
    raw = json.loads(Path(path).read_text())
    reports = _iter_reports(raw)
    passed: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    for report in reports:
        for c in _checks(report, "passed_checks"):
            passed.append(_normalize(c, passed_ok=True))
        for c in _checks(report, "failed_checks"):
            failed.append(_normalize(c, passed_ok=False))
    return {
        "source": str(path),
        "passed": passed,
        "failed": failed,
        "n_passed": len(passed),
        "n_failed": len(failed),
        "n_total": len(passed) + len(failed),
    }
