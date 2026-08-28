"""Adversarial tests for the FAP -> DPIE assurance boundary."""
from datetime import datetime, timezone

from dpie_assurance import AssuranceContext, AssuranceState, Decision, FailureCode, PreservationProof, RuleBinding, State, Transition, evaluate_transition


def _state(state_id: str, *, purpose: str = "claim-verification", jurisdiction: str = "TX", at=None, rule=None):
    at = at or datetime(2026, 8, 28, 14, 0, tzinfo=timezone.utc)
    rule = rule or RuleBinding("carrier-default", "1", "carrier-authority", jurisdiction)
    return State(state_id, {"applicability": AssuranceState.PRESERVED}, AssuranceContext("ADJ-17", purpose, "claim", jurisdiction, at), rule)


def test_verified_claim_cannot_inherit_applicability_after_purpose_shift():
    result = evaluate_transition(Transition("T-PURPOSE-001", _state("Q1"), _state("Q2", purpose="litigation-discovery"), frozenset({"applicability"})), "applicability")
    assert result.decision is Decision.QUARANTINE
    assert result.failure is FailureCode.MISAPPLICATION


def test_verified_claim_cannot_cross_jurisdiction_without_preservation():
    result = evaluate_transition(Transition("T-JURIS-001", _state("Q1"), _state("Q2", jurisdiction="CA"), frozenset({"applicability"})), "applicability")
    assert result.decision is Decision.QUARANTINE
    assert result.failure is FailureCode.JURISDICTION_MISMATCH


def test_unchanged_artifact_still_requires_explicit_preservation_for_material_transition():
    result = evaluate_transition(Transition("T-PRESERVE-001", _state("Q1"), _state("Q2"), frozenset({"applicability"})), "applicability")
    assert result.failure is FailureCode.PRESERVATION_UNESTABLISHED
    assert result.decision is Decision.QUARANTINE


def test_valid_preservation_allows_the_specific_property_to_cross_boundary():
    source = _state("Q1")
    target = _state("Q2", purpose="litigation-discovery")
    proof = PreservationProof(property_name="applicability", transition_id="T-PROOF", rule_id=target.rule.rule_id, rule_version=target.rule.version, authority=target.rule.authority, evidence_refs=(source.state_id,), valid=True, source_purpose=source.context.purpose, target_purpose=target.context.purpose, source_scope=source.context.scope, target_scope=target.context.scope, source_jurisdiction=source.context.jurisdiction, target_jurisdiction=target.context.jurisdiction)
    result = evaluate_transition(Transition("T-PROOF", source, target, frozenset({"applicability"}), preservation={"applicability": proof}), "applicability")
    assert result.state is AssuranceState.PRESERVED
    assert result.decision is Decision.AUTHORIZED
    assert result.failure is FailureCode.NONE


def test_non_material_transition_does_not_force_reverification():
    result = evaluate_transition(Transition("T-NONMAT-001", _state("Q1"), _state("Q2"), frozenset()), "applicability")
    assert result.state is AssuranceState.PRESERVED
    assert result.decision is Decision.AUTHORIZED
