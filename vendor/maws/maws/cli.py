"""MAWS CLI: supervisor run of the unified gate. Shadow by default."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from maws.bootstrap import UNIFIED_ROOT  # noqa: F401 — puts framework on sys.path

from framework.orchestrator import Orchestrator


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="MAWS supervisor: Checkov → named agents → fused go / wait / stop."
    )
    parser.add_argument("checkov_json", type=Path)
    parser.add_argument("--telemetry", type=Path, default=None)
    parser.add_argument("--service", default="maws")
    parser.add_argument("--autonomy", type=int, default=2, choices=(0, 1, 2, 3))
    parser.add_argument("--enforce", action="store_true")
    parser.add_argument("--audit", type=Path, default=None)
    args = parser.parse_args(argv)

    result = Orchestrator(args.audit).run(
        args.checkov_json,
        args.telemetry,
        autonomy=args.autonomy,
        shadow=not args.enforce,
        service=args.service,
    )
    print(json.dumps(result, indent=2))
    if args.enforce and result["governance"]["decision"]["dsa"] == "BLOCK":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
