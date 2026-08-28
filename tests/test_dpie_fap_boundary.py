"""Adversarial tests for the FAP -> DPIE assurance boundary."""
from dpie_assurance import AssuranceState, AssuranceTransition, Decision, Materiality, PreservationProof, Property, evaluate_transition


def _state(**overrides):
    base = {
        "state_id": "FAP-EV-TEST-001",
        "properties": {Property.INTEGRITY: AssuranceState.VALID, Property.PROVENANCE: AssuranceState.VALID, Property.IDENTITY: AssuranceState.VALID, Property.EVIDENCE: AssuranceState.VALID},
        "context": {"purpose": "claim_verification", "jurisdiction": "TX"},
        "rule_id": "fap-insurance-v0.3",
        "rule_version": "0.3.0",
        "authority_id": "carrier-adjuster",
    }
    base.update(overrides)
    return base


def test_verified_claim_cannot_inherit_applicability_after_purpose_shift():
    transition = AssuranceTransition("T-PURPOSE-001", _state(), _state(state_id="Q2", context={"purpose": "litigation", "jurisdiction": "TX"}), Materiality.MATERIAL, ())
    result = evaluate_transition(transition, Property.APPLICABILITY)
    assert result.decision == Decision.DENY
    assert result.reason_code == "MISAPPLICATION"


def test_verified_claim_cannot_cross_jurisdiction_without_preservation():
    transition = AssuranceTransition("T-JURIS-001", _state(), _state(state_id="Q2", context={"purpose": "claim_verification", "jurisdiction": "CA"}), Materiality.MATERIAL, ())
    assert evaluate_transition(transition, Property.APPLICABILITY).decision == Decision.DENY


def test_explicit_preservation_is_required_even_when_artifact_is_unchanged():
    before = _state()
    after = _state(state_id="Q2")
    proof = PreservationProof(property=Property.INTEGRITY, rule_id="fap-insurance-v0.3", rule_version="0.3.0", authority="carrier-adjuster", evidence_refs=("FAP-EV-TEST-001",))
    transition = AssuranceTransition("T-PRESERVE-001", before, after, Materiality.MATERIAL, (proof,))
    assert evaluate_transition(transition, Property.INTEGRITY).decision != Decision.DENY


def test_non_material_transition_does_not_force_reverification():
    transition = AssuranceTransition("T-NONMAT-001", _state(), _state(state_id="Q2", context={"purpose": "claim_verification", "jurisdiction": "TX", "ui_locale": "en-US"}), Materiality.NON_MATERIAL, ())
    assert evaluate_transition(transition, Property.INTEGRITY).decision != Decision.DENY
