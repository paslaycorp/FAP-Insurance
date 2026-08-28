"""Explicit composition boundary for independently verified properties."""
from __future__ import annotations
from dataclasses import dataclass
from dpie_assurance import AssuranceState, Decision, FailureCode

@dataclass(frozen=True)
class CompositionResult:
    state: AssuranceState
    decision: Decision
    failure: FailureCode
    reason: str


def evaluate_composition(*, left: AssuranceState, right: AssuranceState, relation_established: bool) -> CompositionResult:
    """Do not infer a joint assurance property from two valid components."""
    if left in {AssuranceState.UNKNOWN, AssuranceState.CONTRADICTED} or right in {AssuranceState.UNKNOWN, AssuranceState.CONTRADICTED}:
        return CompositionResult(AssuranceState.UNKNOWN, Decision.DEFER, FailureCode.NONE,
                                 "A required dependency is unknown; composition is epistemically unresolved.")
    if not relation_established:
        return CompositionResult(AssuranceState.UNKNOWN, Decision.QUARANTINE, FailureCode.COMPOSITION_UNRESOLVED,
                                 "Both component properties may be valid, but their relationship was not established.")
    if left in {AssuranceState.PRESERVED, AssuranceState.VALID} and right in {AssuranceState.PRESERVED, AssuranceState.VALID}:
        return CompositionResult(AssuranceState.PRESERVED, Decision.AUTHORIZED, FailureCode.NONE,
                                 "Explicit relation establishes the composed assurance property.")
    return CompositionResult(AssuranceState.UNKNOWN, Decision.DEFER, FailureCode.NONE,
                             "Component assurance is not established.")
