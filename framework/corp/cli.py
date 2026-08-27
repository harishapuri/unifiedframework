"""Argparse helpers shared by the fused CLI and plane CLIs."""

from __future__ import annotations

import argparse
import os
import tempfile
from pathlib import Path
from typing import Any

from framework.corp.attach import attach
from framework.ingest.scanners import write_merged


def add_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--actor", default=None, help="Who ran the gate (else GATE_ACTOR / GITHUB_ACTOR)")
    parser.add_argument("--merge-sarif", action="append", default=[], type=Path, help="SARIF file to fold into the scan")
    parser.add_argument("--merge-trivy", action="append", default=[], type=Path, help="Trivy JSON to fold into the scan")
    parser.add_argument("--export-evidence", type=Path, default=None, help="Directory for sealed evidence JSON")
    parser.add_argument("--traffic-intent", type=Path, default=None, help="Directory for blue/green intent JSON")
    parser.add_argument("--traffic-webhook", default=None, help="POST intent here (apply stays false)")
    parser.add_argument("--evidence-webhook", default=None, help="POST evidence packet here")


def prepare_checkov(checkov_json: Path, args: argparse.Namespace) -> Path:
    sarif = list(args.merge_sarif or [])
    trivy = list(args.merge_trivy or [])
    if not sarif and not trivy:
        return checkov_json
    handle = tempfile.NamedTemporaryFile(prefix="merged-scan-", suffix=".json", delete=False)
    handle.close()
    return write_merged(checkov_json, sarif=sarif, trivy=trivy, dest=handle.name)


def finish(result: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    return attach(
        result,
        actor=args.actor or os.environ.get("GATE_ACTOR"),
        export_evidence=args.export_evidence,
        traffic_intent=args.traffic_intent,
        traffic_webhook=args.traffic_webhook,
        evidence_webhook=args.evidence_webhook,
    )
