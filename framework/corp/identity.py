"""Who ran the gate — env first, never the secret itself."""

from __future__ import annotations

import os
from typing import Any


def resolve_actor(explicit: str | None = None) -> dict[str, Any]:
    actor = (explicit or os.environ.get("GATE_ACTOR") or os.environ.get("GITHUB_ACTOR") or "").strip()
    token_set = bool(os.environ.get("GATE_TOKEN") or os.environ.get("EVIDENCE_WEBHOOK_TOKEN"))
    return {
        "actor": actor or "anonymous",
        "token_configured": token_set,
        "source": "flag" if explicit else ("GATE_ACTOR" if os.environ.get("GATE_ACTOR") else ("GITHUB_ACTOR" if os.environ.get("GITHUB_ACTOR") else "anonymous")),
    }
