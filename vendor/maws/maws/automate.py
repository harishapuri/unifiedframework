"""Headless automation: every hive story must match the fused pick."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

from maws.bootstrap import UNIFIED_ROOT  # noqa: F401
from maws.catalog import EXPECTED, STORIES, STORY_ORDER

from framework.orchestrator import Orchestrator


def run_story(key: str, audit_path: Path) -> dict:
    checkov, telemetry, service, blurb = STORIES[key]
    result = Orchestrator(audit_path).run(checkov, telemetry, service=service, shadow=True)
    decision = result["governance"]["decision"]
    want = EXPECTED[key]
    got = (decision["dsa"], decision["action"])
    return {
        "story": key,
        "blurb": blurb,
        "dsa": decision["dsa"],
        "action": decision["action"],
        "expected": {"dsa": want[0], "action": want[1]},
        "ok": got == want,
        "orchestrator": result["governance"].get("orchestrator"),
        "compensation": (result["governance"].get("compensation") or {}).get("policy"),
        "reasons": decision["reasons"],
        "audit_hash": result["governance"]["audit"]["hash"][:12],
    }


def run_all(keys: list[str]) -> list[dict]:
    tmp = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
    tmp.close()
    return [run_story(key, Path(tmp.name)) for key in keys]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Automate MAWS hive demo stories.")
    parser.add_argument("--story", default="all")
    args = parser.parse_args(argv)
    keys = STORY_ORDER if args.story == "all" else [args.story]
    if args.story != "all" and args.story not in STORIES:
        print(f"unknown story {args.story!r}", file=sys.stderr)
        return 2
    rows = run_all(keys)
    print(json.dumps({"plane": "maws", "stories": rows, "passed": all(r["ok"] for r in rows)}, indent=2))
    return 0 if all(r["ok"] for r in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
