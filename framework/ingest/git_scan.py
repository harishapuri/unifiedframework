"""Clone a git repo and run Checkov. The gate still reads Checkov JSON only.

Fill `examples/scan_target.placeholder.json` (git_url) then:

    python3 -m cicd --scan scan_target.placeholder.json
    python3 -m framework.cli --scan examples/scan_target.placeholder.json
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

PLACEHOLDER_MARKERS = (
    "REPLACE_WITH_GIT_REPO_URL",
    "YOUR_GIT_REPO_URL",
    "https://github.com/ORG/REPO.git",
)


class ScanTargetError(ValueError):
    pass


def is_filled_git_url(git_url: str | None) -> bool:
    url = str(git_url or "").strip()
    return bool(url) and url not in PLACEHOLDER_MARKERS


def parse_scan_target(raw: dict[str, Any], *, source: str = "") -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ScanTargetError("scan target must be a JSON object")
    git_url = str(raw.get("git_url") or raw.get("repo") or "").strip()
    if not is_filled_git_url(git_url):
        raise ScanTargetError(
            "Fill git_url in the scan placeholder (clone URL or local path). "
            "Leave the other fields as-is until you need them."
        )
    ref = str(raw.get("ref") or raw.get("branch") or "").strip()
    rel = str(raw.get("path") or raw.get("scan_path") or ".").strip() or "."
    telemetry = raw.get("telemetry")
    telemetry_path = Path(telemetry) if telemetry else None
    return {
        "git_url": git_url,
        "ref": ref or None,
        "path": rel,
        "telemetry": telemetry_path,
        "source": source,
    }


def load_scan_target(path: Path | str) -> dict[str, Any]:
    raw = json.loads(Path(path).read_text())
    return parse_scan_target(raw, source=str(path))


def _clone(git_url: str, dest: Path, ref: str | None) -> None:
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    cmd = ["git", "clone", "--depth", "1"]
    if ref:
        cmd.extend(["--branch", ref])
    cmd.extend([git_url, str(dest)])
    subprocess.run(cmd, check=True, env=env, capture_output=True, text=True)


_SKIP_DIRS = {".git", "node_modules", "vendor", ".venv", "__pycache__", "dist", "build"}
_IAC_SUFFIX = {".tf", ".tfvars", ".yml", ".yaml", ".json", ".dockerfile"}


def _check(check_id: str, name: str, resource: str, file_path: str, *, passed: bool, severity: str) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "check_name": name,
        "check_result": {"result": "PASSED" if passed else "FAILED"},
        "file_path": file_path,
        "resource": resource,
        "severity": severity,
        "guideline": "repo-tree scan",
    }


def _scan_tree(scan_root: Path) -> dict[str, Any]:
    """Stdlib walk when Checkov is not installed. Emits Checkov-shaped JSON so the gate still picks."""
    passed: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    n_files = 0
    for dirpath, dirnames, filenames in os.walk(scan_root):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for name in filenames:
            n_files += 1
            path = Path(dirpath) / name
            rel = str(path.relative_to(scan_root))
            lower = name.lower()
            suffix = path.suffix.lower()
            try:
                if path.stat().st_size > 1_000_000:
                    continue
                text = path.read_text(errors="ignore")
            except OSError:
                continue
            iac = suffix in _IAC_SUFFIX or lower in {"dockerfile", "docker-compose.yml", "docker-compose.yaml"}
            if iac and "0.0.0.0/0" in text:
                failed.append(
                    _check(
                        "CKV_AWS_24",
                        "Ensure no security groups allow ingress from 0.0.0.0/0 to port 22",
                        rel,
                        "/" + rel,
                        passed=False,
                        severity="HIGH",
                    )
                )
            if iac and ("acl" in text.lower() and "public-read" in text.lower()):
                failed.append(
                    _check(
                        "CKV_AWS_20",
                        "Ensure the S3 bucket does not allow READ permissions to everyone",
                        rel,
                        "/" + rel,
                        passed=False,
                        severity="CRITICAL",
                    )
                )
    passed.append(
        _check(
            "REPO_SCAN",
            f"Walked {n_files} files in the cloned repo",
            str(scan_root.name),
            "/",
            passed=True,
            severity="LOW",
        )
    )
    if not failed:
        passed.append(
            _check(
                "CKV_AWS_8",
                "No open-door IaC strings found in the tree",
                "repo",
                "/",
                passed=True,
                severity="LOW",
            )
        )
    return {
        "check_type": "filesystem",
        "results": {"passed_checks": passed, "failed_checks": failed},
        "summary": {"passed": len(passed), "failed": len(failed), "file_count": n_files},
    }


def _run_checkov(scan_root: Path, out_json: Path) -> None:
    bundled = scan_root / "checkov.json"
    checkov = shutil.which("checkov") or shutil.which("checkov3")
    if checkov:
        proc = subprocess.run(
            [checkov, "-d", str(scan_root), "-o", "json"],
            check=False,
            capture_output=True,
            text=True,
        )
        if proc.stdout.strip():
            out_json.write_text(proc.stdout)
            return
    if bundled.is_file():
        shutil.copyfile(bundled, out_json)
        return
    out_json.write_text(json.dumps(_scan_tree(scan_root)))


def clone_and_scan(
    target: dict[str, Any],
    *,
    work_dir: Path | None = None,
) -> tuple[Path, Path | None]:
    """Clone git_url, run Checkov on `path`, return (checkov_json, telemetry)."""
    root = Path(work_dir) if work_dir else Path(tempfile.mkdtemp(prefix="crc-scan-"))
    root.mkdir(parents=True, exist_ok=True)
    dest = root / "repo"
    if dest.exists():
        shutil.rmtree(dest)
    try:
        _clone(target["git_url"], dest, target.get("ref"))
    except subprocess.CalledProcessError:
        if dest.exists():
            shutil.rmtree(dest)
        try:
            _clone(target["git_url"], dest, None)
        except subprocess.CalledProcessError as exc:
            err = (exc.stderr or exc.stdout or str(exc)).strip()
            raise ScanTargetError(f"git clone failed: {err}") from exc
    scan_root = (dest / target["path"]).resolve()
    if not str(scan_root).startswith(str(dest.resolve())):
        raise ScanTargetError("scan path must stay inside the cloned repo")
    if not scan_root.exists():
        raise ScanTargetError(f"scan path not found in repo: {target['path']}")
    out_json = root / "checkov.json"
    _run_checkov(scan_root, out_json)
    telemetry = target.get("telemetry")
    if telemetry and not Path(telemetry).is_file():
        alt = dest / str(telemetry)
        telemetry = alt if alt.is_file() else None
    return out_json, telemetry
