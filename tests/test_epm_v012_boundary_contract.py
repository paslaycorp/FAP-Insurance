from datetime import UTC, datetime

import pytest
from epm import PreservationProof

from epm_fap_adapter import assess_fap_via_epm_envelope
from epm_fap_semantics import (
    FAPDecisionContext,
    preservation_proof_from_mapping,
    source_state_from_fap,
)

AT = datetime(2026, 9, 15, 6, 0, tzinfo=UTC)
TRANSITION_ID = "fap-contract:boundary-1"


def _context(*, purpose: str) -> FAPDecisionContext:
    return FAPDecisionContext(
        identity="subject",
        purpose=purpose,
        scope="claim-record",
        jurisdiction="US-TX",
        at=AT,
        rule_id="claim-rule",
        rule_version="1",
        rule_authority="fap-authority",
        consequence="critical",
    )


def _raw_proof() -> dict:
    return {
        "property_name": "applicability",
        "transition_id": TRANSITION_ID,
        "rule_id": "claim-rule",
        "rule_version": "1",
        "authority": "fap-authority",
        "evidence_refs": ["receipt:123"],
        "valid": True,
        "boundary_validated": True,
        "source_purpose": "review",
        "target_purpose": "secondary-use",
        "source_scope": "claim-record",
        "target_scope": "claim-record",
        "source_jurisdiction": "US-TX",
        "target_jurisdiction": "US-TX",
    }


@pytest.mark.parametrize("verdict", ["STRICT", "PROBABLE"])
def test_fap_verdict_alone_never_becomes_epm_preserved(verdict):
    state = source_state_from_fap(
        "evidence-1",
        {"verdict": verdict, "confidence": 0.999},
        _context(purpose="review"),
    )

    assert set(state.properties.values()) == {state.properties["applicability"]}
    assert state.properties["applicability"].value == "UNKNOWN"


def test_raw_mapping_cannot_self_assert_boundary_validation():
    proof = preservation_proof_from_mapping(_raw_proof(), TRANSITION_ID)

    assert proof is not None
    assert proof.valid is True
    assert proof.boundary_validated is False


def test_raw_proof_mapping_cannot_authorize_material_transition():
    result = assess_fap_via_epm_envelope(
        evidence_id="evidence-1",
        verification={"verdict": "STRICT"},
        source_context=_context(purpose="review"),
        target_context=_context(purpose="secondary-use"),
        transition_id=TRANSITION_ID,
        preservation_proof=_raw_proof(),
    )

    assert result["state"] == "UNKNOWN"
    assert result["decision"] == "DEFER"
    assert result["decision"] != "AUTHORIZED"


def test_boundary_validated_typed_proof_is_rejected_at_raw_fap_boundary():
    proof = PreservationProof(
        property_name="applicability",
        transition_id=TRANSITION_ID,
        rule_id="claim-rule",
        rule_version="1",
        authority="fap-authority",
        evidence_refs=("receipt:validated",),
        valid=True,
        boundary_validated=True,
    )

    with pytest.raises(ValueError, match="dedicated trusted validation adapter"):
        assess_fap_via_epm_envelope(
            evidence_id="evidence-1",
            verification={"verdict": "STRICT"},
            source_context=_context(purpose="review"),
            target_context=_context(purpose="secondary-use"),
            transition_id=TRANSITION_ID,
            preservation_proof=proof,
        )
