"""Fold SARIF and Trivy JSON into Checkov-shaped reports the gate already scores.

The fusion math does not change. Extra scanners become more failed/passed checks
on the same bus. Unknown files are rejected rather than silently dropped.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class ScannerIngestError(ValueError):
    pass


def _check(
    check_id: str,
    name: str,
    resource: str,
    file_path: str,
    *,
    passed: bool,
    severity: str | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "check_id": check_id,
        "check_name": name,
        "resource": resource,
        "file_path": file_path,
        "guideline": "",
    }
    if severity:
        row["severity"] = severity
    return row


def _report(passed: list[dict[str, Any]], failed: list[dict[str, Any]], source: str) -> dict[str, Any]:
    return {
        "check_type": "merged",
        "results": {"passed_checks": passed, "failed_checks": failed},
        "summary": {
            "passed": len(passed),
            "failed": len(failed),
            "resource_count": len(passed) + len(failed),
        },
        "source": source,
    }


def sarif_to_checkov(path: Path | str) -> dict[str, Any]:
    raw = json.loads(Path(path).read_text())
    if not isinstance(raw, dict) or "runs" not in raw:
        raise ScannerIngestError(f"{path} is not SARIF (missing runs)")
    passed: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    for run in raw.get("runs") or []:
        if not isinstance(run, dict):
            continue
        for result in run.get("results") or []:
            if not isinstance(result, dict):
                continue
            rule = str(result.get("ruleId") or "SARIF")
            msg = result.get("message") or {}
            text = str(msg.get("text") if isinstance(msg, dict) else msg or rule)
            loc = ""
            resource = ""
            locs = result.get("locations") or []
            if locs and isinstance(locs[0], dict):
                phys = (locs[0].get("physicalLocation") or {}).get("artifactLocation") or {}
                loc = str(phys.get("uri") or "")
                logical = locs[0].get("logicalLocations") or []
                if logical and isinstance(logical[0], dict):
                    resource = str(logical[0].get("fullyQualifiedName") or logical[0].get("name") or "")
            level = str(result.get("level") or "warning").lower()
            row = _check(rule, text, resource or loc, loc, passed=level in {"none", "note"}, severity=level)
            if level in {"error", "warning"}:
                failed.append(row)
            else:
                passed.append(row)
    return _report(passed, failed, str(path))


def trivy_to_checkov(path: Path | str) -> dict[str, Any]:
    raw = json.loads(Path(path).read_text())
    if not isinstance(raw, dict) or "Results" not in raw:
        raise ScannerIngestError(f"{path} is not Trivy JSON (missing Results)")
    passed: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    for block in raw.get("Results") or []:
        if not isinstance(block, dict):
            continue
        target = str(block.get("Target") or "")
        for mis in block.get("Misconfigurations") or []:
            if not isinstance(mis, dict):
                continue
            cid = str(mis.get("ID") or mis.get("AVDID") or "TRIVY")
            title = str(mis.get("Title") or cid)
            sev = str(mis.get("Severity") or "")
            status = str(mis.get("Status") or "FAIL").upper()
            row = _check(cid, title, str(mis.get("CauseMetadata", {}).get("Resource") or target), target, passed=status == "PASS", severity=sev)
            if status == "PASS":
                passed.append(row)
            else:
                failed.append(row)
        for vuln in block.get("Vulnerabilities") or []:
            if not isinstance(vuln, dict):
                continue
            vid = str(vuln.get("VulnerabilityID") or "CVE")
            title = str(vuln.get("Title") or vid)
            sev = str(vuln.get("Severity") or "")
            pkg = str(vuln.get("PkgName") or "")
            row = _check(vid, title, pkg, target, passed=False, severity=sev)
            failed.append(row)
    return _report(passed, failed, str(path))


def load_checkov_report(path: Path | str) -> dict[str, Any]:
    raw = json.loads(Path(path).read_text())
    if isinstance(raw, dict) and ("results" in raw or "summary" in raw):
        raw.setdefault("source", str(path))
        return raw
    if isinstance(raw, dict) and "runs" in raw:
        return sarif_to_checkov(path)
    if isinstance(raw, dict) and "Results" in raw:
        return trivy_to_checkov(path)
    raise ScannerIngestError(f"{path} is not Checkov, SARIF, or Trivy JSON")


def merge_reports(reports: list[dict[str, Any]]) -> dict[str, Any]:
    passed: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    sources: list[str] = []
    for report in reports:
        sources.append(str(report.get("source") or "unknown"))
        results = report.get("results") or {}
        passed.extend(c for c in (results.get("passed_checks") or []) if isinstance(c, dict))
        failed.extend(c for c in (results.get("failed_checks") or []) if isinstance(c, dict))
    return _report(passed, failed, "+".join(sources))


def write_merged(
    checkov_path: Path | str,
    *,
    sarif: list[Path | str] | None = None,
    trivy: list[Path | str] | None = None,
    dest: Path | str,
) -> Path:
    reports = [load_checkov_report(checkov_path)]
    for path in sarif or []:
        reports.append(sarif_to_checkov(path))
    for path in trivy or []:
        reports.append(trivy_to_checkov(path))
    out = Path(dest)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(merge_reports(reports), indent=2))
    return out
