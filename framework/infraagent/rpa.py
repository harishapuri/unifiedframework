"""Rollout suggestions only — never applied by the gate.

Templates stay rule-based on purpose. A human (or a later ticket bot) applies
the change. Auto-merging chatbot or IAM patches is the least safe upgrade.
"""

from __future__ import annotations

from typing import Any


def suggest(decision: dict[str, Any], infra: dict[str, Any]) -> dict[str, Any]:
    dsa = decision.get("dsa")
    phi_1h = float(infra.get("phi_1h") or 0)
    kappa = float(infra.get("kappa") or 0)
    proposals: list[dict[str, Any]] = []
    if dsa == "BLOCK":
        if phi_1h > 0.85:
            proposals.append(
                {
                    "type": "rollback",
                    "text": "Roll back to the last stable chatbot. Do not move customers.",
                }
            )
        else:
            proposals.append(
                {
                    "type": "hold",
                    "text": "Hold the release. Fix the blocking finding, then run the gate again.",
                }
            )
    elif dsa == "WARN" and kappa > 0.15:
        proposals.append(
            {
                "type": "scale",
                "text": "Add headroom before the switch (HPA min +2, max +4).",
                "patch": {"hpa_min_replicas": "+2", "hpa_max_replicas": "+4"},
            }
        )
    elif dsa == "WARN":
        proposals.append(
            {
                "type": "canary",
                "text": "Ship 10% of chat traffic to green. Bake 30 minutes.",
                "canary_weight": 0.1,
                "bake_time_min": 30,
            }
        )
    else:
        proposals.append({"type": "promote", "text": "Gate says go. Move customers to the new chatbot."})
    return {
        "apply": False,
        "suggest_only": True,
        "proposals": [{**p, "apply": False} for p in proposals],
    }
