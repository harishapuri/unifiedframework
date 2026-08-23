"""Prometheus / Datadog / flat JSON → canonical gate metrics.

Accepts the original flat keys, common aliases, nested exporter objects,
Datadog `series`, Prometheus query results, and an optional `history`
window used by CFA / φ.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULTS = {
    "error_rate": 0.01,
    "cpu": 0.40,
    "latency_p95_ms": 180.0,
    "capacity": 1.0,
    "demand_forecast": 0.45,
    "privilege_excess": 0.20,
    "drift": 0.05,
}

# Last matching alias wins only if the canonical key was not set in the file.
_ALIASES: dict[str, tuple[str, ...]] = {
    "error_rate": (
        "error_rate",
        "errors",
        "error.rate",
        "http_error_rate",
        "http.request.errors",
        "trace.http.request.errors",
        "system.err",
    ),
    "cpu": (
        "cpu",
        "cpu_usage",
        "cpu.usage",
        "system.cpu.user",
        "system.cpu.pct",
    ),
    "latency_p95_ms": (
        "latency_p95_ms",
        "latency_p95",
        "p95",
        "latency.p95",
        "trace.http.request.duration.p95",
        "http_request_duration_p95",
    ),
    "capacity": (
        "capacity",
        "replicas",
        "hpa.current",
        "kube_hpa_status_current_replicas",
    ),
    "demand_forecast": (
        "demand_forecast",
        "demand",
        "rps",
        "req_rate",
        "http.request.rate",
        "requests_per_second",
    ),
    "privilege_excess": (
        "privilege_excess",
        "iam_excess",
        "wildcard_iam",
    ),
    "drift": (
        "drift",
        "config_drift",
        "iac_drift",
    ),
}


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    if isinstance(value, list) and value:
        return _as_float(value[-1] if not isinstance(value[-1], (list, tuple)) else value[-1][-1])
    return None


def _walk(obj: Any, prefix: str = "") -> list[tuple[str, float]]:
    found: list[tuple[str, float]] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in ("history", "series", "points", "values", "data"):
                continue
            path = f"{prefix}.{key}" if prefix else str(key)
            found.extend(_walk(value, path))
            number = _as_float(value)
            if number is not None:
                found.append((str(key), number))
                found.append((path, number))
    return found


def _from_datadog_series(raw: dict[str, Any]) -> dict[str, float]:
    out: dict[str, float] = {}
    series = raw.get("series")
    if not isinstance(series, list):
        return out
    for row in series:
        if not isinstance(row, dict):
            continue
        name = str(row.get("metric") or row.get("name") or "")
        points = row.get("points") or row.get("values") or []
        if not points:
            continue
        last = points[-1]
        number = _as_float(last[1] if isinstance(last, (list, tuple)) and len(last) > 1 else last)
        if number is None:
            continue
        out[name] = number
        out[name.split(".")[-1]] = number
    return out


def _from_prometheus(raw: dict[str, Any]) -> dict[str, float]:
    out: dict[str, float] = {}
    data = raw.get("data")
    if not isinstance(data, dict):
        return out
    result = data.get("result")
    if not isinstance(result, list):
        return out
    for row in result:
        if not isinstance(row, dict):
            continue
        metric = row.get("metric") or {}
        name = str(metric.get("__name__") or metric.get("metric") or "")
        value = row.get("value") or row.get("values")
        number = _as_float(value)
        if number is None or not name:
            continue
        out[name] = number
        out[name.split("_")[-1]] = number
    return out


def _history(raw: dict[str, Any]) -> dict[str, list[float]]:
    hist = raw.get("history")
    series: dict[str, list[float]] = {}
    if isinstance(hist, dict):
        for key, values in hist.items():
            if isinstance(values, list):
                nums = [n for n in (_as_float(v) for v in values) if n is not None]
                if nums:
                    series[str(key)] = nums
    elif isinstance(hist, list):
        buckets: dict[str, list[float]] = {}
        for row in hist:
            if not isinstance(row, dict):
                continue
            for key, value in row.items():
                number = _as_float(value)
                if number is None:
                    continue
                buckets.setdefault(str(key), []).append(number)
        series = buckets
    for key in ("error_rate", "cpu", "demand", "demand_forecast", "latency_p95_ms"):
        values = raw.get(key)
        if isinstance(values, list):
            nums = [n for n in (_as_float(v) for v in values) if n is not None]
            if nums:
                series[key] = nums
    return series


def _pick(aliases: tuple[str, ...], discovered: dict[str, float], raw: dict[str, Any]) -> float | None:
    for alias in aliases:
        if alias in raw:
            number = _as_float(raw[alias])
            if number is not None:
                return number
        lower = {k.lower(): v for k, v in discovered.items()}
        if alias.lower() in lower:
            return lower[alias.lower()]
        for key, value in discovered.items():
            if key.lower().endswith(alias.lower()) or alias.lower() in key.lower():
                return value
    return None


def normalize_telemetry(raw: dict[str, Any]) -> dict[str, Any]:
    """Map any supported exporter blob onto the gate's canonical floats."""
    discovered = dict(_from_datadog_series(raw))
    discovered.update(_from_prometheus(raw))
    for key, value in _walk(raw):
        discovered[key] = value

    out = dict(DEFAULTS)
    explicit: set[str] = set()
    for key in DEFAULTS:
        if key in raw and _as_float(raw[key]) is not None:
            out[key] = float(_as_float(raw[key]))
            explicit.add(key)
        else:
            picked = _pick(_ALIASES[key], discovered, raw)
            if picked is not None:
                out[key] = picked

    history = _history(raw)
    if history:
        out["history"] = history
        # History fills demand only when the file did not set it explicitly.
        demand_series = history.get("demand") or history.get("demand_forecast") or history.get("rps")
        if demand_series and "demand_forecast" not in explicit and "demand_forecast" not in raw:
            out["demand_forecast"] = demand_series[-1]
    return out


def load_telemetry(path: Path | str | None) -> dict[str, Any]:
    if not path:
        return dict(DEFAULTS)
    raw = json.loads(Path(path).read_text())
    if not isinstance(raw, dict):
        raise ValueError("telemetry JSON must be an object")
    return normalize_telemetry(raw)
