from datetime import UTC, datetime

from epm import PreservationProof

from epm_fap_adapter import assess_fap_via_epm_envelope
from epm_fap_semantics import FAPDecisionContext, preservation_proof_from_mapping

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
        # Hostile/self-asserted input: the adapter must ignore this field.
        "boundary_validated": True,
        "source_purpose": "review",
        "target_purpose": "secondary-use",
        "source_scope": "claim-record",
        "target_scope": "claim-record",
        "source_jurisdiction": "US-TX",
        "target_jurisdiction": "US-TX",
    }


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

    assert result["decision"] != "AUTHORIZED"
    assert result["failure"] == "PRESERVATION_UNESTABLISHED"
    assert result["fail_closed"] is True


def test_explicitly_boundary_validated_typed_proof_can_authorize():
    proof = PreservationProof(
        property_name="applicability",
        transition_id=TRANSITION_ID,
        rule_id="claim-rule",
        rule_version="1",
        authority="fap-authority",
        evidence_refs=("receipt:validated",),
        valid=True,
        boundary_validated=True,
        source_purpose="review",
        target_purpose="secondary-use",
        source_scope="claim-record",
        target_scope="claim-record",
        source_jurisdiction="US-TX",
        target_jurisdiction="US-TX",
    )

    result = assess_fap_via_epm_envelope(
        evidence_id="evidence-1",
        verification={"verdict": "STRICT"},
        source_context=_context(purpose="review"),
        target_context=_context(purpose="secondary-use"),
        transition_id=TRANSITION_ID,
        preservation_proof=proof,
    )

    assert result["decision"] == "AUTHORIZED"
    assert result["failure"] == "NONE"
    assert result["fail_closed"] is False
