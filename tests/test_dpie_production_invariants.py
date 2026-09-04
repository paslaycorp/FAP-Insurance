"""Production invariants for the DPIE assurance boundary."""
from datetime import datetime, timedelta, timezone

from dpie_assurance import (
    AssuranceContext,
    AssuranceState,
    Decision,
    FailureCode,
    Materiality,
    PreservationProof,
    RuleBinding,
    State,
    Transition,
    evaluate_transition,
)

AT = datetime(2026, 8, 28, 14, 0, tzinfo=timezone.utc)


def state(name="Q1", *, rule=None, purpose="claim-adjustment", scope="auto", jurisdiction="TX", at=AT, assurance=AssuranceState.PRESERVED):
    return State(
        name,
        {"applicability": assurance},
        AssuranceContext("ADJ-17", purpose, scope, jurisdiction, at),
        rule or RuleBinding("carrier-default", "1", "carrier-authority", jurisdiction),
    )


def proof(transition_id="T1", *, target=None, authority="carrier-authority", target_purpose=None, target_scope=None):
    return PreservationProof(
        transition_id=transition_id,
        property_name="applicability",
        source_state_id="Q1",
        target_state_id=(target.state_id if target else "Q2"),
        authority=authority,
        valid=True,
        target_purpose=target_purpose,
        target_scope=target_scope,
    )


def test_unknown_source_deferred():
    source, target = state(assurance=AssuranceState.UNKNOWN), state("Q2")
    result = evaluate_transition(Transition("T1", source, target, frozenset({"applicability"})), "applicability")
    assert result.state is AssuranceState.UNKNOWN
    assert result.decision is Decision.DEFER


def test_contradicted_source_deferred():
    source, target = state(assurance=AssuranceState.CONTRADICTED), state("Q2")
    result = evaluate_transition(Transition("T1", source, target, frozenset({"applicability"})), "applicability")
    assert result.state is AssuranceState.UNKNOWN
    assert result.decision is Decision.DEFER


def test_missing_proof_invalidates_material_transition():
    source, target = state(), state("Q2")
    result = evaluate_transition(Transition("T1", source, target, frozenset({"applicability"})), "applicability")
    assert result.state is AssuranceState.INVALIDATED
    assert result.failure is FailureCode.PRESERVATION_UNESTABLISHED


def test_proof_from_wrong_authority_cannot_authorize():
    source, target = state(), state("Q2")
    result = evaluate_transition(
        Transition("T1", source, target, frozenset({"applicability"}), {"applicability": proof(authority="other-authority", target=target)}),
        "applicability",
    )
    assert result.state is AssuranceState.INVALIDATED
    assert result.failure is FailureCode.AUTHORITY_MISMATCH


def test_proof_bound_to_wrong_transition_cannot_be_reused():
    source, target = state(), state("Q2")
    result = evaluate_transition(
        Transition("T2", source, target, frozenset({"applicability"}), {"applicability": proof("T1", target=target)}),
        "applicability",
    )
    assert result.state is AssuranceState.INVALIDATED
    assert result.failure is FailureCode.PRESERVATION_UNESTABLISHED


def test_future_effective_rule_cannot_authorize_current_transition():
    future_rule = RuleBinding("carrier-default", "2", "carrier-authority", "TX", AT.replace(hour=15))
    source, target = state(), state("Q2", rule=future_rule)
    result = evaluate_transition(
        Transition("T1", source, target, frozenset({"applicability"}), {"applicability": proof(target=target)}),
        "applicability",
    )
    assert result.state is AssuranceState.INVALIDATED
    assert result.failure is FailureCode.RULE_MISMATCH


def test_purpose_bound_proof_cannot_cross_to_different_purpose():
    source, target = state(), state("Q2", purpose="litigation-discovery")
    result = evaluate_transition(
        Transition(
            "T1", source, target, frozenset({"applicability"}),
            {"applicability": proof(target=target, target_purpose="claim-adjustment")},
        ),
        "applicability",
    )
    assert result.state is AssuranceState.INVALIDATED
    assert result.failure is FailureCode.MISAPPLICATION


def test_scope_bound_proof_cannot_cross_to_different_scope():
    source, target = state(), state("Q2", scope="property")
    result = evaluate_transition(
        Transition(
            "T1", source, target, frozenset({"applicability"}),
            {"applicability": proof(target=target, target_scope="auto")},
        ),
        "applicability",
    )
    assert result.state is AssuranceState.INVALIDATED
    assert result.failure is FailureCode.MISAPPLICATION


def test_critical_consequence_denies_invalid_transition():
    source, target = state(), state("Q2", purpose="litigation-discovery")
    result = evaluate_transition(
        Transition("T1", source, target, frozenset({"applicability"})),
        "applicability",
        consequence="critical",
    )
    assert result.decision is Decision.DENY


def test_non_material_transition_does_not_invalidate_valid_source():
    source, target = state(), state("Q2")
    result = evaluate_transition(Transition("T1", source, target, frozenset()), "applicability")
    assert result.state is AssuranceState.PRESERVED
    assert result.decision is Decision.AUTHORIZED
