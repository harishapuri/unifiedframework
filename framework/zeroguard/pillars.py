"""ZeroGuard (2143): Checkov → NIST SP 800-207 pillars, Ξ, Γ, Ψ."""

from __future__ import annotations

import math
from typing import Any

LAM = 0.33

PILLARS = (
    "P1_resources",
    "P2_comms",
    "P3_session",
    "P4_dynamic_policy",
    "P5_integrity",
    "P6_authz",
    "P7_telemetry",
)

# Heuristic map: Checkov check-id prefix / keyword → pillars + debt weight 1–4.
_RULES: list[tuple[tuple[str, ...], tuple[str, ...], int]] = [
    (("CKV_AWS_23", "CKV_AWS_24", "CKV_AWS_260", "CKV_AWS_25", "0.0.0.0/0", "security group"), ("P2_comms", "P3_session"), 4),
    (("CKV_AWS_20", "CKV_AWS_53", "CKV_AWS_54", "public", "CKV_AWS_21"), ("P1_resources", "P2_comms"), 4),
    (("CKV_AWS_40", "CKV_AWS_41", "CKV_AWS_45", "CKV_AWS_46", "CKV_AWS_61", "CKV_AWS_62", "wildcard", "iam"), ("P4_dynamic_policy", "P6_authz"), 4),
    (("CKV_AWS_16", "CKV_AWS_3", "CKV_AWS_8", "CKV_AWS_144", "encrypt", "kms"), ("P2_comms", "P5_integrity"), 3),
    (("CKV_AWS_18", "CKV_AWS_50", "CKV_AWS_67", "logging", "cloudtrail", "flow"), ("P7_telemetry", "P5_integrity"), 2),
    (("CKV_AWS_111", "secret", "password"), ("P6_authz", "P2_comms"), 4),
]


def severity_weight(sev: str | None) -> int:
    s = (sev or "").upper()
    return {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1, "NONE": 1}.get(s, 2)


def classify_check(check_id: str, name: str, guideline: str) -> tuple[tuple[str, ...], int]:
    blob = f"{check_id} {name} {guideline}".lower()
    for keys, pillars, debt in _RULES:
        if any(k.lower() in blob for k in keys):
            return pillars, debt
    return ("P5_integrity",), 2


def pillar_scores(failed: list[dict[str, Any]], passed: list[dict[str, Any]]) -> dict[str, float]:
    hits = {p: 0.0 for p in PILLARS}
    tot = {p: 0.0 for p in PILLARS}
    for row in passed + failed:
        for p in row.get("pillars") or []:
            if p not in tot:
                continue
            tot[p] += 1
            if row.get("passed"):
                hits[p] += 1
    scores = {}
    for p in PILLARS:
        scores[p] = (hits[p] / tot[p]) if tot[p] else 0.85
        failed_here = sum(1 for r in failed if p in (r.get("pillars") or []))
        if failed_here and tot[p] == 0:
            scores[p] = 0.2
        elif failed_here:
            scores[p] = min(scores[p], max(0.15, 1.0 - 0.2 * failed_here))
    return scores


def iam_gamma(failed: list[dict[str, Any]], telemetry: dict[str, float]) -> float:
    iam = [
        r
        for r in failed
        if "P6_authz" in (r.get("pillars") or []) or "P4_dynamic_policy" in (r.get("pillars") or [])
    ]
    from_checks = min(1.0, 0.25 * len(iam))
    return max(from_checks, float(telemetry.get("privilege_excess", 0.0)))


def score(
    checkov: dict[str, Any],
    telemetry: dict[str, float],
    *,
    eta: float,
    phi_bar: float,
) -> dict[str, Any]:
    pillars = pillar_scores(checkov["failed"], checkov["passed"])
    xi = sum(pillars.values()) / len(PILLARS)
    delta = float(telemetry.get("drift", 0.0))
    gamma = iam_gamma(checkov["failed"], telemetry)
    psi = math.exp(-LAM * phi_bar) * xi * math.exp(-LAM * delta) * math.exp(-LAM * gamma) * eta
    critical = any(int(r.get("debt") or 0) >= 4 for r in checkov["failed"])
    return {
        "psi": round(psi, 4),
        "xi": round(xi, 4),
        "gamma": round(gamma, 4),
        "delta": round(delta, 4),
        "pillars": {k: round(v, 3) for k, v in pillars.items()},
        "critical_iac": critical,
        "sigma": "critical" if critical else ("high" if checkov["n_failed"] else "ok"),
    }
