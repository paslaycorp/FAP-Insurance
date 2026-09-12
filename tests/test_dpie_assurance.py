from datetime import datetime, timezone

from dpie_assurance import (
    AssuranceContext,
    AssuranceProperty,
    AssuranceState,
    Decision,
    FailureCode,
    PreservationProof,
    RuleBinding,
    State,
    Transition,
    evaluate_transition,
    perfect_artifact_misapplication_demo,
)


def _state(state_id: str, *, purpose: str = "claim-adjustment", jurisdiction: str = "TX", rule=None):
    rule = rule or RuleBinding("carrier-default", "1", "carrier-authority", jurisdiction)
    return State(
        state_id,
        {"applicability": AssuranceState.PRESERVED},
        AssuranceContext(
            identity="ADJ-17",
            purpose=purpose,
            scope="auto",
            jurisdiction=jurisdiction,
            at=datetime(2026, 8, 28, 14, 0, tzinfo=timezone.utc),
        ),
        rule,
    )


def test_perfect_artifact_can_be_misapplied_without_tampering():
    result = perfect_artifact_misapplication_demo()
    assert result.state is AssuranceState.INVALIDATED
    assert result.failure is FailureCode.MISAPPLICATION
    assert result.decision is Decision.DENY


def test_material_transition_does_not_inherit_assurance_without_proof():
    source = _state("Q1")
    target = _state("Q2", purpose="different-purpose")
    result = evaluate_transition(
        Transition("T1", source, target, frozenset({"applicability"})),
        "applicability",
    )
    assert result.failure is FailureCode.MISAPPLICATION
    assert result.decision is Decision.QUARANTINE


def test_valid_preservation_proof_allows_property_to_cross_boundary():
    source = _state("Q1")
    target = _state("Q2")
    transition_id = "T1"
    proof = PreservationProof(
        property_name="applicability",
        transition_id=transition_id,
        rule_id=target.rule.rule_id,
        rule_version=target.rule.version,
        authority=target.rule.authority,
        evidence_refs=("E1", "E2"),
        valid=True,
        reason="Policy scope explicitly permits the transition.",
        source_purpose=source.context.purpose,
        target_purpose=target.context.purpose,
        source_scope=source.context.scope,
        target_scope=target.context.scope,
        source_jurisdiction=source.context.jurisdiction,
        target_jurisdiction=target.context.jurisdiction,
    )
    result = evaluate_transition(
        Transition(
            transition_id,
            source,
            target,
            frozenset({"applicability"}),
            preservation={"applicability": proof},
        ),
        "applicability",
    )
    assert result.state is AssuranceState.PRESERVED
    assert result.decision is Decision.AUTHORIZED
    assert result.failure is FailureCode.NONE


def test_wrong_rule_binding_does_not_count_as_preservation():
    source = _state("Q1")
    target = _state("Q2", rule=RuleBinding("carrier-default", "2", "carrier-authority", "TX"))
    proof = PreservationProof(
        property_name="applicability",
        transition_id="T1",
        rule_id="carrier-default",
        rule_version="1",
        authority="carrier-authority",
        evidence_refs=("E1",),
        valid=True,
        reason="Bound to the previous rule.",
    )
    result = evaluate_transition(
        Transition("T1", source, target, frozenset({"applicability"}), {"applicability": proof}),
        "applicability",
    )
    assert result.failure is FailureCode.RULE_MISMATCH
    assert result.state is AssuranceState.INVALIDATED


def test_jurisdiction_change_is_not_tampering():
    source = _state("Q1", jurisdiction="TX")
    target = _state("Q2", jurisdiction="LA")
    result = evaluate_transition(
        Transition("T1", source, target, frozenset({"applicability"})),
        "applicability",
    )
    assert result.failure is FailureCode.JURISDICTION_MISMATCH
    assert result.decision is Decision.QUARANTINE


def test_non_material_transition_can_preserve_without_new_proof():
    source = _state("Q1")
    target = _state("Q2")
    result = evaluate_transition(
        Transition("T1", source, target, frozenset()),
        "applicability",
    )
    assert result.state is AssuranceState.PRESERVED
    assert result.decision is Decision.AUTHORIZED


def test_assurance_property_has_explicit_dependencies():
    prop = AssuranceProperty("applicability", frozenset({"purpose", "scope", "jurisdiction"}))
    assert "purpose" in prop.dependencies
    assert "scope" in prop.dependencies
    assert "jurisdiction" in prop.dependencies
