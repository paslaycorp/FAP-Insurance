"""First-class EPM constraint semantics.

Constraints are immutable, provenance-bearing semantic objects. Their validity
is evaluated from typed premise, entailment, and governance states; a boolean
flag cannot manufacture a valid narrowing operation.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum


class PremiseState(str, Enum):
    ESTABLISHED = "ESTABLISHED"
    UNKNOWN = "UNKNOWN"
    INVALIDATED = "INVALIDATED"
    CONTRADICTED = "CONTRADICTED"


class EntailmentStatus(str, Enum):
    ESTABLISHED = "ESTABLISHED"
    UNESTABLISHED = "UNESTABLISHED"
    CONTRADICTED = "CONTRADICTED"


class ConstraintReviewStatus(str, Enum):
    NOT_REQUIRED = "NOT_REQUIRED"
    REQUIRED = "REQUIRED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ConstraintStatus(str, Enum):
    VALID = "VALID"
    UNSUPPORTED = "UNSUPPORTED"
    INVALIDATED = "INVALIDATED"
    CONTRADICTED = "CONTRADICTED"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class Constraint:
    constraint_id: str
    proposition: str
    premise_refs: tuple[str, ...]
    premise_states: Mapping[str, PremiseState]
    provenance_refs: tuple[str, ...]
    entailment_basis: str
    entailment_status: EntailmentStatus
    dependency_refs: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    excluded_candidates: tuple[str, ...] = ()
    source_ref: str = ""
    review_status: ConstraintReviewStatus = ConstraintReviewStatus.NOT_REQUIRED
    revision_of: str | None = None


@dataclass(frozen=True)
class ConstraintEvaluation:
    constraint_id: str
    status: ConstraintStatus
    reason_code: str
    reason: str


def evaluate_constraint(constraint: Constraint) -> ConstraintEvaluation:
    if not constraint.constraint_id.strip() or not constraint.proposition.strip():
        return ConstraintEvaluation(
            constraint.constraint_id,
            ConstraintStatus.UNSUPPORTED,
            "CONSTRAINT_IDENTITY_REQUIRED",
            "Constraint identity and proposition are required.",
        )
    if not constraint.premise_refs:
        return ConstraintEvaluation(
            constraint.constraint_id,
            ConstraintStatus.UNSUPPORTED,
            "PREMISES_REQUIRED",
            "A valid narrowing constraint requires identified supporting premises.",
        )
    if not constraint.provenance_refs or any(
        not ref.strip() for ref in constraint.provenance_refs
    ):
        return ConstraintEvaluation(
            constraint.constraint_id,
            ConstraintStatus.UNSUPPORTED,
            "PROVENANCE_REQUIRED",
            "Constraint provenance must be explicit and non-empty.",
        )
    if not constraint.source_ref.strip():
        return ConstraintEvaluation(
            constraint.constraint_id,
            ConstraintStatus.UNSUPPORTED,
            "SOURCE_REQUIRED",
            "Constraint source typing/provenance reference is required.",
        )
    if constraint.review_status is ConstraintReviewStatus.REJECTED:
        return ConstraintEvaluation(
            constraint.constraint_id,
            ConstraintStatus.REJECTED,
            "GOVERNANCE_REJECTED",
            "Required governance review rejected the constraint.",
        )

    states = [
        constraint.premise_states.get(ref, PremiseState.UNKNOWN)
        for ref in constraint.premise_refs
    ]
    if any(state is PremiseState.CONTRADICTED for state in states):
        return ConstraintEvaluation(
            constraint.constraint_id,
            ConstraintStatus.CONTRADICTED,
            "PREMISE_CONTRADICTED",
            "At least one required premise is contradicted.",
        )
    if constraint.entailment_status is EntailmentStatus.CONTRADICTED:
        return ConstraintEvaluation(
            constraint.constraint_id,
            ConstraintStatus.CONTRADICTED,
            "ENTAILMENT_CONTRADICTED",
            "The declared entailment relation is contradicted.",
        )
    if any(state is PremiseState.INVALIDATED for state in states):
        return ConstraintEvaluation(
            constraint.constraint_id,
            ConstraintStatus.INVALIDATED,
            "PREMISE_INVALIDATED",
            "At least one required premise has been invalidated.",
        )
    if any(state is PremiseState.UNKNOWN for state in states):
        return ConstraintEvaluation(
            constraint.constraint_id,
            ConstraintStatus.UNSUPPORTED,
            "PREMISE_UNESTABLISHED",
            "At least one required premise is unknown or missing.",
        )
    if (
        constraint.entailment_status is not EntailmentStatus.ESTABLISHED
        or not constraint.entailment_basis.strip()
    ):
        return ConstraintEvaluation(
            constraint.constraint_id,
            ConstraintStatus.UNSUPPORTED,
            "ENTAILMENT_UNESTABLISHED",
            "Candidate exclusions are not effective without an established entailment basis.",
        )
    if constraint.review_status is ConstraintReviewStatus.REQUIRED:
        return ConstraintEvaluation(
            constraint.constraint_id,
            ConstraintStatus.UNSUPPORTED,
            "GOVERNANCE_REVIEW_REQUIRED",
            "This constraint requires independent governance review before it can narrow the answer-space.",
        )

    return ConstraintEvaluation(
        constraint.constraint_id,
        ConstraintStatus.VALID,
        "CONSTRAINT_VALID",
        "Premises, provenance, entailment, and required governance review are established.",
    )


def effective_exclusions(constraint: Constraint) -> tuple[str, ...]:
    """Return exclusions only for a constraint that is currently valid."""
    evaluation = evaluate_constraint(constraint)
    return (
        constraint.excluded_candidates
        if evaluation.status is ConstraintStatus.VALID
        else ()
    )
