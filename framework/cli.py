"""CLI: fuse Checkov JSON (+ optional telemetry) into one shadow/enforce gate.

Also records what actually happened after a pick, and prints a scorecard
before you turn on `--enforce`.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from framework.orchestrator import Orchestrator  # noqa: E402
from framework.outcome import ACTUALS, record_outcome, scorecard  # noqa: E402


def _run_gate(argv: list[str]) -> int:
    p = argparse.ArgumentParser(
        description="Unified gate: git repo or Checkov JSON → CRC + ZeroGuard + InfraAgent → ALLOW/WARN/BLOCK (shadow by default)."
    )
    p.add_argument("checkov_json", nargs="?", type=Path, help="Path to `checkov -o json` output")
    p.add_argument(
        "--scan",
        type=Path,
        default=None,
        help="Placeholder JSON with git_url (examples/scan_target.placeholder.json).",
    )
    p.add_argument("--telemetry", type=Path, default=None, help="Optional metrics JSON (Prometheus/Datadog export)")
    p.add_argument("--service", default="chatbot-api")
    p.add_argument("--autonomy", type=int, default=2, choices=(0, 1, 2, 3))
    p.add_argument("--enforce", action="store_true", help="Leave shadow mode (exit 2 on BLOCK)")
    p.add_argument("--audit", type=Path, default=None)
    args = p.parse_args(argv)

    from framework.ingest.git_scan import ScanTargetError, clone_and_scan, load_scan_target

    checkov_json = args.checkov_json
    telemetry = args.telemetry
    if args.scan:
        try:
            target = load_scan_target(args.scan)
            checkov_json, scanned_telemetry = clone_and_scan(target)
        except ScanTargetError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        telemetry = telemetry or scanned_telemetry
    elif checkov_json is None:
        p.error("pass a Checkov JSON path, or --scan examples/scan_target.placeholder.json")

    orch = Orchestrator(args.audit)
    result = orch.run(
        checkov_json,
        telemetry,
        autonomy=args.autonomy,
        shadow=not args.enforce,
        service=args.service,
    )
    print(json.dumps(result, indent=2))
    if args.enforce and result["governance"]["decision"]["dsa"] == "BLOCK":
        return 2
    return 0


def _record(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="Record what actually happened after a gate pick.")
    p.add_argument("audit_hash", help="Full hash or unique prefix from the audit row")
    p.add_argument("actual", choices=ACTUALS)
    p.add_argument("--note", default="")
    p.add_argument("--audit", type=Path, default=None)
    p.add_argument("--outcomes", type=Path, default=None)
    args = p.parse_args(argv)
    row = record_outcome(
        args.audit_hash,
        args.actual,
        note=args.note,
        audit_path=args.audit,
        outcomes_path=args.outcomes,
    )
    print(json.dumps(row, indent=2))
    return 0


def _scorecard(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="Join audit picks with later outcomes.")
    p.add_argument("--audit", type=Path, default=None)
    p.add_argument("--outcomes", type=Path, default=None)
    args = p.parse_args(argv)
    print(json.dumps(scorecard(audit_path=args.audit, outcomes_path=args.outcomes), indent=2))
    return 0


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "record-outcome":
        return _record(sys.argv[2:])
    if len(sys.argv) > 1 and sys.argv[1] == "scorecard":
        return _scorecard(sys.argv[2:])
    return _run_gate(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
