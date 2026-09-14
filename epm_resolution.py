"""Answer-space and resolution semantics for EPM vNext."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from enum import Enum

from epm_constraints import Constraint, ConstraintStatus, evaluate_constraint
from epm_sources import (
    EpistemicSourceRecord,
    EpistemicSourceType,
    validate_source_record,
)


class ResolutionState(str, Enum):
    UNRESOLVED = "UNRESOLVED"
    CONSTRAINED = "CONSTRAINED"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class EpistemicStanding(str, Enum):
    UNKNOWN = "UNKNOWN"
    OBSERVED = "OBSERVED"
    EVIDENCED = "EVIDENCED"
    DERIVED = "DERIVED"
    INFERRED = "INFERRED"
    PREDICTED = "PREDICTED"


class AnswerSpaceOperation(str, Enum):
    NARROWED = "NARROWED"
    WIDENED = "WIDENED"
    REOPENED = "REOPENED"
    UNCHANGED = "UNCHANGED"
    DERIVATION_RECORDED = "DERIVATION_RECORDED"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


@dataclass(frozen=True)
class AnswerSpaceHistoryEvent:
    operation: AnswerSpaceOperation
    before: tuple[str, ...]
    after: tuple[str, ...]
    basis_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class AnswerSpaceSnapshot:
    question_id: str
    candidate_universe: tuple[str, ...]
    admissible_candidates: tuple[str, ...]
    resolution_state: ResolutionState
    epistemic_standing: EpistemicStanding
    active_constraint_refs: tuple[str, ...] = ()
    discriminator_refs: tuple[str, ...] = ()
    granularity: str = ""
    granularity_basis: str = ""
    history: tuple[AnswerSpaceHistoryEvent, ...] = ()


@dataclass(frozen=True)
class AnswerSpaceValidation:
    valid: bool
    reason_code: str
    reason: str


@dataclass(frozen=True)
class Discriminator:
    discriminator_id: str
    alternatives: tuple[str, ...]
    observation_partition: Mapping[str, tuple[str, ...]]
    provenance_refs: tuple[str, ...]


@dataclass(frozen=True)
class DiscriminatorAssessment:
    sufficient: bool
    reason_code: str
    reason: str


@dataclass(frozen=True)
class DiscriminatorObservation:
    discriminator_id: str
    observed_value: str
    source: EpistemicSourceRecord


@dataclass(frozen=True)
class ClosureBasis:
    exhaustive_domain: bool
    basis_refs: tuple[str, ...]
    external_resolution_refs: tuple[str, ...]
    unresolved_conditions: tuple[str, ...] = ()


@dataclass(frozen=True)
class ResolutionOperationResult:
    snapshot: AnswerSpaceSnapshot
    applied: bool
    reason_code: str
    reason: str


def create_answer_space(
    *,
    question_id: str,
    candidates: Sequence[str],
    granularity: str,
    granularity_basis: str,
) -> AnswerSpaceSnapshot:
    universe = tuple(dict.fromkeys(str(candidate) for candidate in candidates))
    return AnswerSpaceSnapshot(
        question_id=question_id,
        candidate_universe=universe,
        admissible_candidates=universe,
        resolution_state=ResolutionState.UNRESOLVED,
        epistemic_standing=EpistemicStanding.UNKNOWN,
        granularity=granularity,
        granularity_basis=granularity_basis,
    )


def validate_answer_space(snapshot: AnswerSpaceSnapshot) -> AnswerSpaceValidation:
    if not snapshot.question_id.strip():
        return AnswerSpaceValidation(
            False,
            "QUESTION_REQUIRED",
            "Answer-space requires a question identity.",
        )
    if not snapshot.candidate_universe:
        return AnswerSpaceValidation(
            False,
            "CANDIDATES_REQUIRED",
            "Answer-space requires at least one declared candidate.",
        )
    if len(set(snapshot.candidate_universe)) != len(snapshot.candidate_universe):
        return AnswerSpaceValidation(
            False,
            "CANDIDATES_NOT_UNIQUE",
            "Candidate universe must not silently duplicate alternatives.",
        )
    if not snapshot.granularity.strip() or not snapshot.granularity_basis.strip():
        return AnswerSpaceValidation(
            False,
            "GRANULARITY_BASIS_REQUIRED",
            "Answer-space granularity and its justification must be explicit.",
        )
    if not set(snapshot.admissible_candidates).issubset(
        set(snapshot.candidate_universe)
    ):
        return AnswerSpaceValidation(
            False,
            "ADMISSIBLE_OUTSIDE_UNIVERSE",
            "Admissible candidates must remain inside the declared universe.",
        )
    return AnswerSpaceValidation(
        True,
        "ANSWER_SPACE_VALID",
        "Answer-space representation is explicit and internally consistent.",
    )


def recompute_with_constraints(
    snapshot: AnswerSpaceSnapshot,
    constraints: Sequence[Constraint],
) -> ResolutionOperationResult:
    valid_constraints = [
        constraint
        for constraint in constraints
        if evaluate_constraint(constraint).status is ConstraintStatus.VALID
    ]
    exclusions = {
        candidate
        for constraint in valid_constraints
        for candidate in constraint.excluded_candidates
    }
    after = tuple(
        candidate
        for candidate in snapshot.candidate_universe
        if candidate not in exclusions
    )
    active = tuple(constraint.constraint_id for constraint in valid_constraints)
    before_set, after_set = set(snapshot.admissible_candidates), set(after)
    if after == snapshot.admissible_candidates:
        operation = AnswerSpaceOperation.UNCHANGED
    elif after_set < before_set:
        operation = AnswerSpaceOperation.NARROWED
    elif before_set < after_set:
        removed_constraint = bool(set(snapshot.active_constraint_refs) - set(active))
        operation = (
            AnswerSpaceOperation.REOPENED
            if removed_constraint
            else AnswerSpaceOperation.WIDENED
        )
    else:
        operation = AnswerSpaceOperation.WIDENED

    state = (
        ResolutionState.UNRESOLVED
        if after == snapshot.candidate_universe and not active
        else ResolutionState.CONSTRAINED
    )
    standing = (
        EpistemicStanding.DERIVED if active else snapshot.epistemic_standing
    )
    event = AnswerSpaceHistoryEvent(
        operation,
        snapshot.admissible_candidates,
        after,
        active,
    )
    updated = replace(
        snapshot,
        admissible_candidates=after,
        resolution_state=state,
        epistemic_standing=standing,
        active_constraint_refs=active,
        history=snapshot.history + (event,),
    )
    return ResolutionOperationResult(
        updated,
        True,
        operation.value,
        "Answer-space recomputed from the declared universe and currently valid constraints.",
    )


def record_derivation(
    snapshot: AnswerSpaceSnapshot,
    *,
    candidate: str,
    derivation_ref: str,
) -> ResolutionOperationResult:
    if candidate not in snapshot.admissible_candidates:
        return ResolutionOperationResult(
            snapshot,
            False,
            "CANDIDATE_NOT_ADMISSIBLE",
            "Derivation cannot select a candidate already excluded from the current answer-space.",
        )
    event = AnswerSpaceHistoryEvent(
        AnswerSpaceOperation.DERIVATION_RECORDED,
        snapshot.admissible_candidates,
        snapshot.admissible_candidates,
        (derivation_ref,),
    )
    updated = replace(
        snapshot,
        epistemic_standing=EpistemicStanding.DERIVED,
        history=snapshot.history + (event,),
    )
    return ResolutionOperationResult(
        updated,
        True,
        "DERIVATION_RECORDED",
        "Computation/derivation was recorded without promoting the resolution state.",
    )


def assess_discriminator(
    snapshot: AnswerSpaceSnapshot,
    discriminator: Discriminator,
) -> DiscriminatorAssessment:
    if not discriminator.discriminator_id.strip() or not discriminator.provenance_refs:
        return DiscriminatorAssessment(
            False,
            "DISCRIMINATOR_PROVENANCE_REQUIRED",
            "Discriminator identity and provenance are required.",
        )
    current = set(snapshot.admissible_candidates)
    if not current.issubset(set(discriminator.alternatives)):
        return DiscriminatorAssessment(
            False,
            "DISCRIMINATOR_INCOMPLETE_ALTERNATIVES",
            "Discriminator does not declare every currently admissible alternative.",
        )
    covered = set()
    for partition in discriminator.observation_partition.values():
        relevant = current.intersection(partition)
        covered.update(relevant)
        if len(relevant) > 1:
            return DiscriminatorAssessment(
                False,
                "DISCRIMINATOR_PARTIAL",
                "At least one discriminator outcome leaves multiple current alternatives indistinguishable.",
            )
    if covered != current:
        return DiscriminatorAssessment(
            False,
            "DISCRIMINATOR_INCOMPLETE_PARTITION",
            "Discriminator partition does not cover the current answer-space.",
        )
    return DiscriminatorAssessment(
        True,
        "DISCRIMINATOR_SUFFICIENT",
        "Declared observation partition can distinguish every currently admissible alternative.",
    )


def resolve_with_observation(
    snapshot: AnswerSpaceSnapshot,
    discriminator: Discriminator,
    observation: DiscriminatorObservation,
) -> ResolutionOperationResult:
    if observation.discriminator_id != discriminator.discriminator_id:
        return ResolutionOperationResult(
            snapshot,
            False,
            "DISCRIMINATOR_ID_MISMATCH",
            "Observation is bound to a different discriminator.",
        )
    source_check = validate_source_record(observation.source)
    if (
        not source_check.valid
        or observation.source.source_type is not EpistemicSourceType.OBSERVATION
    ):
        return ResolutionOperationResult(
            snapshot,
            False,
            "OBSERVATION_REQUIRED",
            "Stage 2 resolution requires a valid externally originated observation source.",
        )
    sufficiency = assess_discriminator(snapshot, discriminator)
    if not sufficiency.sufficient:
        return ResolutionOperationResult(
            snapshot,
            False,
            sufficiency.reason_code,
            sufficiency.reason,
        )
    selected = tuple(
        candidate
        for candidate in discriminator.observation_partition.get(
            observation.observed_value,
            (),
        )
        if candidate in snapshot.admissible_candidates
    )
    if len(selected) != 1:
        return ResolutionOperationResult(
            snapshot,
            False,
            "OBSERVATION_NOT_RESOLVING",
            "Observed discriminator value does not select exactly one currently admissible answer.",
        )
    event = AnswerSpaceHistoryEvent(
        AnswerSpaceOperation.RESOLVED,
        snapshot.admissible_candidates,
        selected,
        (discriminator.discriminator_id, observation.source.source_id),
    )
    updated = replace(
        snapshot,
        admissible_candidates=selected,
        resolution_state=ResolutionState.RESOLVED,
        epistemic_standing=EpistemicStanding.EVIDENCED,
        discriminator_refs=tuple(
            dict.fromkeys(
                snapshot.discriminator_refs + (discriminator.discriminator_id,)
            )
        ),
        history=snapshot.history + (event,),
    )
    return ResolutionOperationResult(
        updated,
        True,
        "RESOLVED_BY_OBSERVATION",
        "A sufficient discriminator and new external observation resolved the answer-space.",
    )


def close_answer_space(
    snapshot: AnswerSpaceSnapshot,
    closure: ClosureBasis,
) -> ResolutionOperationResult:
    if snapshot.resolution_state is not ResolutionState.RESOLVED:
        return ResolutionOperationResult(
            snapshot,
            False,
            "RESOLUTION_REQUIRED",
            "Closure requires a legitimately resolved answer-space.",
        )
    if not closure.exhaustive_domain:
        return ResolutionOperationResult(
            snapshot,
            False,
            "EXHAUSTIVE_DOMAIN_REQUIRED",
            "Closure requires an explicit claim that the declared candidate domain is exhaustive at the stated granularity.",
        )
    if not closure.basis_refs:
        return ResolutionOperationResult(
            snapshot,
            False,
            "CLOSURE_BASIS_REQUIRED",
            "Closure provenance/basis references are required.",
        )
    if not closure.external_resolution_refs:
        return ResolutionOperationResult(
            snapshot,
            False,
            "EXTERNAL_RESOLUTION_REQUIRED",
            "Closure cannot be manufactured solely by computation over unchanged evidence.",
        )
    if closure.unresolved_conditions:
        return ResolutionOperationResult(
            snapshot,
            False,
            "UNRESOLVED_CONDITIONS_REMAIN",
            "Material unresolved conditions prevent closure.",
        )
    if snapshot.epistemic_standing in {
        EpistemicStanding.UNKNOWN,
        EpistemicStanding.DERIVED,
    }:
        return ResolutionOperationResult(
            snapshot,
            False,
            "EPISTEMIC_STANDING_INSUFFICIENT",
            "Derived or unknown standing cannot be promoted to closure without legitimate external resolution evidence.",
        )
    event = AnswerSpaceHistoryEvent(
        AnswerSpaceOperation.CLOSED,
        snapshot.admissible_candidates,
        snapshot.admissible_candidates,
        closure.basis_refs + closure.external_resolution_refs,
    )
    updated = replace(
        snapshot,
        resolution_state=ResolutionState.CLOSED,
        history=snapshot.history + (event,),
    )
    return ResolutionOperationResult(
        updated,
        True,
        "ANSWER_SPACE_CLOSED",
        "Resolution and explicit exhaustive closure basis are established.",
    )
