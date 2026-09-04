from datetime import datetime, timezone

from dpie_assurance import (
    AssuranceContext,
    AssuranceState,
    Decision,
    FailureCode,
    PreservationProof,
    RuleBinding,
    State,
    Transition,
    evaluate_transition,
)


AT = datetime(2026, 8, 28, 14, 0, tzinfo=timezone.utc)


def state(state_id="Q1", *, purpose="claim-adjustment", scope="auto", jurisdiction="TX", rule=None, value=AssuranceState.PRESERVED):
    rule = rule or RuleBinding("carrier-default", "1", "carrier-authority", jurisdiction)
    return State(
        state_id,
        {"applicability": value},
        AssuranceContext("ADJ-17", purpose, scope, jurisdiction, AT),
        rule,
    )


def proof(transition_id="T1", *, target, **overrides):
    values = dict(
        property_name="applicability",
        transition_id=transition_id,
        rule_id=target.rule.rule_id,
        rule_version=target.rule.version,
        authority=target.rule.authority,
        evidence_refs=("E1",),
        valid=True,
    )
    values.update(overrides)
    return PreservationProof(**values)


def test_unknown_source_defers_without_fabricating_invalidity():
    result = evaluate_transition(
        Transition("T1", state(value=AssuranceState.UNKNOWN), state("Q2"), frozenset({"applicability"})),
        "applicability",
    )
    assert result.state is AssuranceState.UNKNOWN
    assert result.decision is Decision.DEFER


def test_contradicted_source_defers():
    result = evaluate_transition(
        Transition("T1", state(value=AssuranceState.CONTRADICTED), state("Q2"), frozenset({"applicability"})),
        "applicability",
    )
    assert result.state is AssuranceState.UNKNOWN
    assert result.decision is Decision.DEFER


def test_missing_evidence_refs_cannot_establish_preservation():
    source, target = state(), state("Q2")
    result = evaluate_transition(
        Transition("T1", source, target, frozenset({"applicability"}), {"applicability": proof(target=target, evidence_refs=())}),
        "applicability",
    )
    assert result.state is AssuranceState.INVALIDATED
    assert result.failure is FailureCode.PRESERVATION_UNESTABLISHED


def test_wrong_authority_cannot_establish_preservation():
    source, target = state(), state("Q2")
    result = evaluate_transition(
        Transition("T1", source, target, frozenset({"applicability"}), {"applicability": proof(target=target, authority="other-authority")}),
        "applicability",
    )
    assert result.failure is FailureCode.AUTHORITY_MISMATCH
    assert result.decision is Decision.QUARANTINE


def test_invalidated_proof_cannot_establish_preservation():
    source, target = state(), state("Q2")
    result = evaluate_transition(
        Transition("T1", source, target, frozenset({"applicability"}), {"applicability": proof(target=target, valid=False)}),
        "applicability",
    )
    assert result.state is AssuranceState.INVALIDATED
    assert result.failure is FailureCode.PRESERVATION_UNESTABLISHED


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


def test_critical_consequence_fails_closed_to_deny():
    source, target = state(), state("Q2", jurisdiction="LA")
    result = evaluate_transition(
        Transition("T1", source, target, frozenset({"applicability"})),
        "applicability",
        consequence="critical",
    )
    assert result.decision is Decision.DENY
    assert result.failure is FailureCode.JURISDICTION_MISMATCH


def test_non_material_transition_does_not_require_preservation_proof():
    source, target = state(), state("Q2", purpose="different-purpose")
    result = evaluate_transition(Transition("T1", source, target, frozenset()), "applicability")
    assert result.state is AssuranceState.PRESERVED
    assert result.decision is Decision.AUTHORIZED
