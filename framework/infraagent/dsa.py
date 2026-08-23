"""DSA + CRC fused gate (InfraAgent Eq. 7 plus residual / ZTA critical).

Constrained DQN (later) cannot ALLOW through a DSA BLOCK. This module is the
hard gate; RL may only choose among actions that do not weaken a BLOCK.
"""

from __future__ import annotations

from typing import Any

ACTIONS = ("ALLOW", "WARN", "BLOCK_BUILD", "BLOCK_DEPLOYMENT", "ROLLBACK")


def decide(scores: dict[str, Any], *, autonomy: int = 2) -> dict[str, Any]:
    """Return a gate decision. autonomy α0–α3; α2 is the paper default."""
    phi1 = float(scores["phi_1h"])
    phi6 = float(scores["phi_6h"])
    residual = bool(scores["residual_high"])
    critical = bool(scores["critical_iac"])
    pillar_fail = any(v < 0.5 for v in scores["pillars"].values())
    k = float(scores["kappa"])

    reasons: list[str] = []
    dsa = "PASS"
    if phi1 > 0.7:
        dsa = "BLOCK"
        reasons.append(f"phi_1h={phi1:.2f} > 0.7")
    elif residual or critical:
        dsa = "BLOCK"
        reasons.append("CRC residual-high or ZTPA-critical IaC")
    elif phi6 > 0.5:
        dsa = "WARN"
        reasons.append(f"phi_6h={phi6:.2f} > 0.5")
    elif pillar_fail:
        dsa = "WARN"
        reasons.append("ZTA pillar below 0.5")
    elif k > 0.15:
        dsa = "WARN"
        reasons.append(f"capacity deficit kappa={k:.2f}")

    if dsa == "BLOCK":
        action = "BLOCK_DEPLOYMENT" if (phi1 > 0.7 or residual) else "BLOCK_BUILD"
        if phi1 > 0.85 and float(scores.get("phi_bar_debt", 0)) < 0.2:
            action = "ROLLBACK"
        gate = "FAIL"
    elif dsa == "WARN":
        action = "WARN"
        gate = "WARN"
    else:
        action = "ALLOW"
        gate = "PASS"

    # α0 never recommends enforcement; α1 annotates; α2+ may enforce in CLI.
    enforce = autonomy >= 2 and dsa == "BLOCK"
    annotate = autonomy >= 1

    return {
        "dsa": dsa,
        "gate": gate,
        "action": action,
        "reasons": reasons or ["all fused scores within PASS bounds"],
        "autonomy": autonomy,
        "would_enforce": enforce,
        "annotate_pr": annotate and dsa != "PASS",
        "dqn_may_allow": dsa != "BLOCK",
    }
