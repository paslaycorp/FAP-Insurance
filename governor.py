"""Decision Governor for consequential DPIE outcomes.

The Governor does not verify evidence or establish semantic preservation. It
maps an already evaluated assurance state to an admissibility decision under
the declared consequence class.
"""
from __future__ import annotations

from dpie_assurance import AssuranceState, Decision, FailureCode


def govern(*, assurance_state: AssuranceState, failure: FailureCode, consequence: str) -> Decision:
    consequence = consequence.lower()
    if assurance_state is AssuranceState.UNKNOWN:
        return Decision.DEFER
    if failure is FailureCode.NONE and assurance_state is AssuranceState.PRESERVED:
        return Decision.AUTHORIZED
    if consequence == "critical":
        return Decision.DENY
    return Decision.QUARANTINE
