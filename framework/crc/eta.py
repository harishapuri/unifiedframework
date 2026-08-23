"""CRC (207): η = passed / total; residual-high from failed-check debt."""

from __future__ import annotations

from typing import Any


def eta(n_passed: int, n_total: int) -> float:
    if n_total <= 0:
        return 1.0
    return n_passed / n_total


def mean_debt(failed: list[dict[str, Any]]) -> float:
    if not failed:
        return 0.0
    return sum(float(r.get("debt") or 0) for r in failed) / (4.0 * len(failed))


def score(checkov: dict[str, Any]) -> dict[str, Any]:
    n_p, n_t = checkov["n_passed"], checkov["n_total"]
    n_f = checkov["n_failed"]
    e = eta(n_p, n_t)
    phi_bar = mean_debt(checkov["failed"])
    critical = any(int(r.get("debt") or 0) >= 4 for r in checkov["failed"])
    residual_high = n_f > 0 and (phi_bar >= 0.35 or critical)
    return {
        "eta": round(e, 4),
        "phi_bar_debt": round(phi_bar, 4),
        "n_passed": n_p,
        "n_failed": n_f,
        "n_total": n_t,
        "critical_iac": critical,
        "residual_high": residual_high,
    }
