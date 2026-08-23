"""InfraAgent (1239): heuristic φ horizons, capacity deficit κ, posture Ω.

Snapshot path is unchanged. When `history` is present, Holt smoothing
fills demand (CFA) and a rising error trend lifts φ_6h. Swap this file
later for XGBoost / Prophet without changing the orchestrator contract.
"""

from __future__ import annotations

import math
from typing import Any

ALPHA = 0.33


def holt_forecast(values: list[float], *, alpha: float = 0.4, beta: float = 0.2, horizon: int = 1) -> float:
    """One-step Holt linear forecast. Short series → last value."""
    xs = [float(x) for x in values if x is not None]
    if not xs:
        return 0.0
    if len(xs) == 1:
        return xs[0]
    level = xs[0]
    trend = xs[1] - xs[0]
    for x in xs[1:]:
        prev = level
        level = alpha * x + (1 - alpha) * (level + trend)
        trend = beta * (level - prev) + (1 - beta) * trend
    return max(0.0, level + horizon * trend)


def _rising(values: list[float]) -> bool:
    if len(values) < 3:
        return False
    tail = values[-3:]
    return tail[-1] > tail[0] and tail[-1] >= tail[-2]


def apply_history(telemetry: dict[str, Any]) -> dict[str, Any]:
    """Copy telemetry and overlay CFA demand from a real window when present."""
    out = dict(telemetry)
    history = telemetry.get("history")
    if not isinstance(history, dict):
        return out
    demand = history.get("demand") or history.get("demand_forecast") or history.get("rps")
    if isinstance(demand, list) and demand and "demand_forecast" not in telemetry.get("_explicit", {}):
        # Recompute whenever history carries demand — load_telemetry already
        # left explicit file-level demand_forecast in place.
        if telemetry.get("_demand_locked"):
            return out
        out["demand_forecast"] = holt_forecast([float(x) for x in demand])
        out["cfa_source"] = "holt"
    return out


def phi_from_telemetry(telemetry: dict[str, Any]) -> dict[str, float]:
    err = float(telemetry["error_rate"])
    cpu = float(telemetry["cpu"])
    lat = float(telemetry["latency_p95_ms"])
    base = 1.0 / (1.0 + math.exp(-(6.0 * (err - 0.05) + 2.5 * (cpu - 0.75) + 0.004 * (lat - 400))))
    phi_1h = min(0.99, base)
    phi_6h = min(0.99, base * 0.85 + 0.05 * cpu)
    phi_24h = min(0.99, base * 0.7 + 0.08 * cpu)
    history = telemetry.get("history")
    if isinstance(history, dict):
        errors = history.get("error_rate")
        if isinstance(errors, list) and _rising([float(x) for x in errors]):
            phi_6h = min(0.99, max(phi_6h, phi_1h * 0.95 + 0.08))
            phi_24h = min(0.99, max(phi_24h, phi_6h * 0.9 + 0.04))
    return {"phi_1h": phi_1h, "phi_6h": phi_6h, "phi_24h": phi_24h}


def kappa(telemetry: dict[str, Any]) -> float:
    return max(0.0, float(telemetry["demand_forecast"]) - float(telemetry["capacity"]))


def score(telemetry: dict[str, Any], *, eta: float) -> dict[str, Any]:
    prepared = apply_history(telemetry)
    # If the file set demand_forecast itself, load_telemetry kept it. History
    # still forecasts when demand_forecast was only a last-point fill.
    history = telemetry.get("history")
    if isinstance(history, dict):
        demand = history.get("demand") or history.get("demand_forecast") or history.get("rps")
        raw_demand = telemetry.get("demand_forecast")
        last = float(demand[-1]) if isinstance(demand, list) and demand else None
        if demand and last is not None and abs(float(raw_demand) - last) < 1e-9:
            prepared["demand_forecast"] = holt_forecast([float(x) for x in demand])
            prepared["cfa_source"] = "holt"
    phis = phi_from_telemetry(prepared)
    k = kappa(prepared)
    delta = float(prepared.get("drift", 0.0))
    phi_mean = (phis["phi_1h"] + phis["phi_6h"] + phis["phi_24h"]) / 3.0
    omega = math.exp(-ALPHA * phi_mean) * math.exp(-ALPHA * k) * math.exp(-ALPHA * delta) * eta
    return {
        "omega": round(omega, 4),
        "kappa": round(k, 4),
        "delta": round(delta, 4),
        "cfa_source": prepared.get("cfa_source", "snapshot"),
        **{key: round(value, 4) for key, value in phis.items()},
    }
