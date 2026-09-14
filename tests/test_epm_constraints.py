"""Adversarial gate for the EPM first-class constraint model v0.1."""
from dataclasses import replace

from epm_constraints import (
    Constraint,
    ConstraintReviewStatus,
    ConstraintStatus,
    EntailmentStatus,
    PremiseState,
    effective_exclusions,
    evaluate_constraint,
)


def _constraint(**overrides) -> Constraint:
    base = Constraint(
        constraint_id="CST-1",
        proposition="Candidate Y is excluded by established premise P1.",
        premise_refs=("P1",),
        premise_states={"P1": PremiseState.ESTABLISHED},
        provenance_refs=("prov:P1", "prov:CST-1"),
        entailment_basis="P1 logically excludes Y under declared domain rule R1.",
        entailment_status=EntailmentStatus.ESTABLISHED,
        dependency_refs=("P1",),
        assumptions=("R1 applies to the represented answer domain",),
        excluded_candidates=("Y",),
        source_ref="source:CST-1",
        review_status=ConstraintReviewStatus.NOT_REQUIRED,
    )
    return replace(base, **overrides)


def test_valid_constraint_requires_premises_provenance_and_entailment():
    result = evaluate_constraint(_constraint())
    assert result.status is ConstraintStatus.VALID
    assert effective_exclusions(_constraint()) == ("Y",)


def test_plausible_but_unestablished_entailment_is_unsupported():
    constraint = _constraint(entailment_status=EntailmentStatus.UNESTABLISHED)
    result = evaluate_constraint(constraint)
    assert result.status is ConstraintStatus.UNSUPPORTED
    assert result.reason_code == "ENTAILMENT_UNESTABLISHED"
    assert effective_exclusions(constraint) == ()


def test_invalidated_premise_invalidates_constraint_and_exclusions():
    constraint = _constraint(premise_states={"P1": PremiseState.INVALIDATED})
    result = evaluate_constraint(constraint)
    assert result.status is ConstraintStatus.INVALIDATED
    assert result.reason_code == "PREMISE_INVALIDATED"
    assert effective_exclusions(constraint) == ()


def test_contradicted_premise_marks_constraint_contradicted():
    constraint = _constraint(premise_states={"P1": PremiseState.CONTRADICTED})
    result = evaluate_constraint(constraint)
    assert result.status is ConstraintStatus.CONTRADICTED
    assert effective_exclusions(constraint) == ()


def test_adversarial_narrowing_requiring_review_cannot_self_authorize():
    constraint = _constraint(review_status=ConstraintReviewStatus.REQUIRED)
    result = evaluate_constraint(constraint)
    assert result.status is ConstraintStatus.UNSUPPORTED
    assert result.reason_code == "GOVERNANCE_REVIEW_REQUIRED"
    assert effective_exclusions(constraint) == ()


def test_governance_rejection_is_preserved_as_rejected():
    result = evaluate_constraint(_constraint(review_status=ConstraintReviewStatus.REJECTED))
    assert result.status is ConstraintStatus.REJECTED
    assert result.reason_code == "GOVERNANCE_REJECTED"


def test_approved_review_does_not_repair_missing_entailment():
    constraint = _constraint(
        review_status=ConstraintReviewStatus.APPROVED,
        entailment_status=EntailmentStatus.UNESTABLISHED,
    )
    result = evaluate_constraint(constraint)
    assert result.status is ConstraintStatus.UNSUPPORTED
    assert result.reason_code == "ENTAILMENT_UNESTABLISHED"


def test_revision_is_new_immutable_constraint_linked_to_predecessor():
    original = _constraint()
    revision = replace(
        original,
        constraint_id="CST-2",
        revision_of=original.constraint_id,
        excluded_candidates=("X",),
    )
    assert original.constraint_id == "CST-1"
    assert original.excluded_candidates == ("Y",)
    assert revision.constraint_id == "CST-2"
    assert revision.revision_of == "CST-1"
    assert revision.excluded_candidates == ("X",)
