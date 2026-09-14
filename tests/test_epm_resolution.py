"""Adversarial gate for EPM answer-space and resolution state v0.1."""
from dataclasses import replace

from epm_constraints import (
    Constraint,
    EntailmentStatus,
    PremiseState,
)
from epm_resolution import (
    AnswerSpaceOperation,
    ClosureBasis,
    Discriminator,
    DiscriminatorObservation,
    EpistemicStanding,
    ResolutionState,
    assess_discriminator,
    close_answer_space,
    create_answer_space,
    recompute_with_constraints,
    record_derivation,
    resolve_with_observation,
    validate_answer_space,
)
from epm_sources import EpistemicSourceRecord, EpistemicSourceType


def _space():
    return create_answer_space(
        question_id="Q-1",
        candidates=("X", "Y"),
        granularity="binary candidate identity",
        granularity_basis="The declared question has exactly the represented X/Y alternatives for this test domain.",
    )


def _constraint(*, premise_state=PremiseState.ESTABLISHED):
    return Constraint(
        constraint_id="CST-Y",
        proposition="Y is excluded.",
        premise_refs=("P1",),
        premise_states={"P1": premise_state},
        provenance_refs=("prov:P1",),
        entailment_basis="P1 entails exclusion of Y.",
        entailment_status=EntailmentStatus.ESTABLISHED,
        excluded_candidates=("Y",),
        source_ref="source:CST-Y",
    )


def _sufficient_discriminator():
    return Discriminator(
        discriminator_id="D-1",
        alternatives=("X", "Y"),
        observation_partition={"x-signal": ("X",), "y-signal": ("Y",)},
        provenance_refs=("prov:D-1",),
    )


def _observation(value="x-signal", source_type=EpistemicSourceType.OBSERVATION):
    return DiscriminatorObservation(
        discriminator_id="D-1",
        observed_value=value,
        source=EpistemicSourceRecord(
            source_id="OBS-D1",
            source_type=source_type,
            producer="external-sensor",
            provenance_refs=("prov:OBS-D1",),
            external_origin=source_type is EpistemicSourceType.OBSERVATION,
        ),
    )


def test_singleton_from_constraint_remains_constrained_not_resolved():
    result = recompute_with_constraints(_space(), (_constraint(),))
    assert result.snapshot.admissible_candidates == ("X",)
    assert result.snapshot.resolution_state is ResolutionState.CONSTRAINED
    assert result.snapshot.epistemic_standing is EpistemicStanding.DERIVED


def test_stronger_computation_remains_derived_and_does_not_close():
    constrained = recompute_with_constraints(_space(), (_constraint(),)).snapshot
    derived = record_derivation(constrained, candidate="X", derivation_ref="calc:stronger-engine")
    assert derived.applied is True
    assert derived.snapshot.epistemic_standing is EpistemicStanding.DERIVED
    assert derived.snapshot.resolution_state is ResolutionState.CONSTRAINED
    closure = close_answer_space(
        derived.snapshot,
        ClosureBasis(True, ("closure:domain",), ("external:missing",)),
    )
    assert closure.applied is False
    assert closure.reason_code == "RESOLUTION_REQUIRED"


def test_insufficient_discriminator_cannot_resolve_current_alternatives():
    discriminator = Discriminator(
        discriminator_id="D-WEAK",
        alternatives=("X", "Y"),
        observation_partition={"same-signal": ("X", "Y")},
        provenance_refs=("prov:D-WEAK",),
    )
    assessment = assess_discriminator(_space(), discriminator)
    assert assessment.sufficient is False
    assert assessment.reason_code == "DISCRIMINATOR_PARTIAL"


def test_discriminator_definition_cannot_serve_as_its_own_observation():
    result = resolve_with_observation(
        _space(),
        _sufficient_discriminator(),
        _observation(source_type=EpistemicSourceType.DISCRIMINATOR),
    )
    assert result.applied is False
    assert result.reason_code == "OBSERVATION_REQUIRED"
    assert result.snapshot.resolution_state is ResolutionState.UNRESOLVED


def test_valid_external_observation_and_sufficient_discriminator_resolve():
    result = resolve_with_observation(_space(), _sufficient_discriminator(), _observation())
    assert result.applied is True
    assert result.snapshot.admissible_candidates == ("X",)
    assert result.snapshot.resolution_state is ResolutionState.RESOLVED
    assert result.snapshot.epistemic_standing is EpistemicStanding.EVIDENCED


def test_resolution_does_not_become_closed_without_explicit_exhaustive_basis():
    resolved = resolve_with_observation(_space(), _sufficient_discriminator(), _observation()).snapshot
    missing = close_answer_space(
        resolved,
        ClosureBasis(False, ("closure:domain",), ("prov:OBS-D1",)),
    )
    assert missing.applied is False
    assert missing.reason_code == "EXHAUSTIVE_DOMAIN_REQUIRED"
    closed = close_answer_space(
        resolved,
        ClosureBasis(True, ("closure:domain",), ("prov:OBS-D1",)),
    )
    assert closed.applied is True
    assert closed.snapshot.resolution_state is ResolutionState.CLOSED


def test_invalidated_constraint_reopens_candidate_from_preserved_universe():
    constrained = recompute_with_constraints(_space(), (_constraint(),)).snapshot
    assert constrained.admissible_candidates == ("X",)
    invalidated = replace(
        _constraint(),
        premise_states={"P1": PremiseState.INVALIDATED},
    )
    reopened = recompute_with_constraints(constrained, (invalidated,))
    assert reopened.snapshot.admissible_candidates == ("X", "Y")
    assert reopened.snapshot.resolution_state is ResolutionState.UNRESOLVED
    assert reopened.snapshot.history[-1].operation is AnswerSpaceOperation.REOPENED


def test_missing_granularity_basis_invalidates_answer_space_representation():
    invalid = create_answer_space(
        question_id="Q-GRANULARITY",
        candidates=("X", "Y"),
        granularity="binary",
        granularity_basis="",
    )
    validation = validate_answer_space(invalid)
    assert validation.valid is False
    assert validation.reason_code == "GRANULARITY_BASIS_REQUIRED"
