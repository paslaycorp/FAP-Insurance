"""Adversarial tests for the FAP -> DPIE assurance boundary.

These tests deliberately keep evidence authentic while changing the downstream
assurance conditions. The objective is to prove that verified evidence does
not silently become an authorized decision.
"""

from dpie_assurance import (
    AssuranceState,
    AssuranceTransition,
    Decision,
    Materiality,
    PreservationProof,
    Property,
    evaluate_transition,
)


def _state(**overrides):
    base = dict(
        state_id="FAP-EV-TEST-001",
        properties={
            Property.INTEGRITY: AssuranceState.VALID,
            Property.PROVENANCE: AssuranceState.VALID,
            Property.IDENTITY: AssuranceState.VALID,
            Property.EVIDENCE: AssuranceState.VALID,
        },
        context={"purpose": "claim_verification", "jurisdiction": "TX"},
        rule_id="fap-insurance-v0.3",
        rule_version="0.3.0",
        authority_id="carrier-adjuster",
    )
    base.update(overrides)
    return base


def test_verified_claim_cannot_inherit_applicability_after_purpose_shift():
    before = _state()
    after = _state(state_id="Q2", context={"purpose": "litigation", "jurisdiction": "TX"})
    transition = AssuranceTransition(
        transition_id="T-PURPOSE-001",
        source_state=before,
        target_state=after,
        materiality=Materiality.MATERIAL,
        preservation_proofs=(),
    )
    result = evaluate_transition(transition, Property.APPLICABILITY)
    assert result.decision == Decision.DENY
    assert result.reason_code == "MISAPPLICATION"


def test_verified_claim_cannot_cross_jurisdiction_without_preservation():
    before = _state()
    after = _state(state_id="Q2", context={"purpose": "claim_verification", "jurisdiction": "CA"})
    transition = AssuranceTransition(
        transition_id="T-JURIS-001",
        source_state=before,
        target_state=after,
        materiality=Materiality.MATERIAL,
        preservation_proofs=(),
    )
    result = evaluate_transition(transition, Property.APPLICABILITY)
    assert result.decision == Decision.DENY


def test_explicit_preservation_is_required_even_when_artifact_is_unchanged():
    before = _state()
    after = _state(state_id="Q2")
    transition = AssuranceTransition(
        transition_id="T-PRESERVE-001",
        source_state=before,
        target_state=after,
        materiality=Materiality.MATERIAL,
        preservation_proofs=(
            PreservationProof(
                property=Property.INTEGRITY,
                rule_id="dpie-preservation",
                rule_version="1.0.0",
                evidence_refs=("FAP-EV-TEST-001",),
            ),
        ),
    )
    result = evaluate_transition(transition, Property.INTEGRITY)
    assert result.decision != Decision.DENY


def test_non_material_transition_does_not_force_reverification():
    before = _state()
    after = _state(state_id="Q2", context={"purpose": "claim_verification", "jurisdiction": "TX", "ui_locale": "en-US"})
    transition = AssuranceTransition(
        transition_id="T-NONMAT-001",
        source_state=before,
        target_state=after,
        materiality=Materiality.NON_MATERIAL,
        preservation_proofs=(),
    )
    result = evaluate_transition(transition, Property.INTEGRITY)
    assert result.decision != Decision.DENY
