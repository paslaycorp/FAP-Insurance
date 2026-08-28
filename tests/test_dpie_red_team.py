from datetime import datetime, timezone

from dpie_assurance import AssuranceContext, AssuranceState, FailureCode, PreservationProof, RuleBinding, State, Transition, Decision, evaluate_transition
from dpie_runtime import FAPDecisionContext, assess_fap_transition


def state(state_id="Q", purpose="claim-adjustment", jurisdiction="TX", at=None, rule=None, value=AssuranceState.PRESERVED):
    at = at or datetime(2026, 8, 28, 14, 0, tzinfo=timezone.utc)
    rule = rule or RuleBinding("carrier-default", "1", "carrier-authority", jurisdiction)
    return State(state_id, {"applicability": value}, AssuranceContext("ADJ-17", purpose, "auto", jurisdiction, at), rule)


def test_authentic_changed_purpose_is_misapplication():
    result = evaluate_transition(Transition("T-A", state(), state("Q2", "litigation-discovery"), frozenset({"applicability"})), "applicability")
    assert result.failure is FailureCode.MISAPPLICATION
    assert result.decision is Decision.QUARANTINE


def test_jurisdiction_rule_time_boundaries_are_distinct():
    assert evaluate_transition(Transition("T-J", state(), state("Q2", jurisdiction="LA"), frozenset({"applicability"})), "applicability").failure is FailureCode.JURISDICTION_MISMATCH
    assert evaluate_transition(Transition("T-R", state(), state("Q2", rule=RuleBinding("carrier-default", "2", "carrier-authority", "TX")), frozenset({"applicability"})), "applicability").failure is FailureCode.RULE_MISMATCH
    later = datetime(2026, 8, 29, 14, 0, tzinfo=timezone.utc)
    assert evaluate_transition(Transition("T-T", state(), state("Q2", at=later), frozenset({"applicability"})), "applicability").failure is FailureCode.TEMPORAL_MISMATCH


def test_unknown_does_not_become_invalid():
    result = evaluate_transition(Transition("T-U", state(value=AssuranceState.UNKNOWN), state("Q2"), frozenset({"applicability"})), "applicability", consequence="critical")
    assert result.state is AssuranceState.UNKNOWN
    assert result.decision is Decision.DEFER
    assert result.failure is FailureCode.NONE


def test_unauthorized_preservation_proof_is_rejected():
    source, target = state(), state("Q2", "litigation-discovery")
    proof = PreservationProof(property_name="applicability", transition_id="T-P", rule_id=target.rule.rule_id,
                              rule_version=target.rule.version, authority="wrong-authority", evidence_refs=("E1",), valid=True)
    result = evaluate_transition(Transition("T-P", source, target, frozenset({"applicability"}), {"applicability": proof}), "applicability")
    assert result.failure is FailureCode.AUTHORITY_MISMATCH


def test_preservation_proof_scoped_to_wrong_purpose_is_rejected():
    source, target = state(), state("Q2", "litigation-discovery")
    proof = PreservationProof(property_name="applicability", transition_id="T-P2", rule_id=target.rule.rule_id,
                              rule_version=target.rule.version, authority=target.rule.authority, evidence_refs=("E1",),
                              valid=True, target_purpose="another-purpose")
    result = evaluate_transition(Transition("T-P2", source, target, frozenset({"applicability"}), {"applicability": proof}), "applicability")
    assert result.failure is FailureCode.MISAPPLICATION


def test_valid_preservation_crosses_boundary():
    source, target = state(), state("Q2", "litigation-discovery")
    proof = PreservationProof(property_name="applicability", transition_id="T-P3", rule_id=target.rule.rule_id,
                              rule_version=target.rule.version, authority=target.rule.authority, evidence_refs=("E1",),
                              valid=True, source_purpose=source.context.purpose, target_purpose=target.context.purpose,
                              source_scope=source.context.scope, target_scope=target.context.scope,
                              source_jurisdiction=source.context.jurisdiction, target_jurisdiction=target.context.jurisdiction)
    result = evaluate_transition(Transition("T-P3", source, target, frozenset({"applicability"}), {"applicability": proof}), "applicability")
    assert result.failure is FailureCode.NONE
    assert result.state is AssuranceState.PRESERVED


def test_runtime_preserves_unknown_as_defer():
    source = FAPDecisionContext("ADJ-17", "claim-adjustment", "auto", "TX", datetime(2026, 8, 28, tzinfo=timezone.utc), "carrier-default", "1", "carrier-authority")
    target = FAPDecisionContext("ADJ-17", "claim-adjustment", "auto", "TX", source.at, "carrier-default", "1", "carrier-authority", "critical")
    result = assess_fap_transition(evidence_id="E-1", verification={"verdict": "UNKNOWN"}, source_context=source, target_context=target, transition_id="T-RUNTIME")
    assert result["state"] == "UNKNOWN"
    assert result["decision"] == "DEFER"
