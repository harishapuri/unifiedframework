"""Corporate adapters around the fused gate.

These do not change η × Ψ × Ω, do not auto-apply patches, and do not turn on
`--enforce`. They stamp an actor, merge extra scanners, emit a traffic *intent*
for the platform mesh, and copy the sealed audit row to a folder or webhook.
"""

from framework.corp.attach import attach
from framework.corp.identity import resolve_actor

__all__ = ["attach", "resolve_actor"]
