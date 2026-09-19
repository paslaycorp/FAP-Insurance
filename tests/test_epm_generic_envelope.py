"""vNext adversarial probes for the Generic Evidentiary Envelope v0.1."""
from datetime import datetime, timedelta, timezone

from dpie_assurance import AssuranceContext, AssuranceState, RuleBinding, State
from dpie_runtime import FAPDecisionContext, assess_fap_transition
from epm import PreservationProof
from epm_envelope import EvidentiaryEnvelope, evaluate_evidentiary_envelope
from epm_fap_adapter import assess_fap_via_epm_envelope

UTC = timezone.utc
AT = datetime(2026, 8, 28, 14, 0, tzinfo=UTC)


def _context(
    *,
    purpose: str = "claim-verification",
    scope: str = "claim",
    jurisdiction: str = "TX",
    at: datetime = AT,
    rule_id: str = "carrier-default",
    rule_version: str = "1",
    authority: str = "carrier-authority",
    consequence: str = "standard",
) -> FAPDecisionContext:
    return FAPDecisionContext(
        None,
        purpose,
        scope,
        jurisdiction,
        at,
        rule_id,
        rule_version,
        authority,
        consequence,
    )


def _legacy_shape(result):
    normalized = dict(result)
    normalized.pop("schema_version", None)
    return normalized


def test_generic_envelope_does_not_promote_unknown_to_requested_preserved():
    rule = RuleBinding("generic-rule", "1", "generic-authority", "TX", AT)
    context = AssuranceContext(None, "review", "record", "TX", AT)
    source = State(
        "E-GENERIC-UNKNOWN",
        {"applicability": AssuranceState.UNKNOWN},
        context,
        rule,
    )
    target = State(
        "E-GENERIC-UNKNOWN:target",
        {"applicability": AssuranceState.PRESERVED},
        context,
        rule,
    )
    envelope = EvidentiaryEnvelope(
        transition_id="T-GENERIC-UNKNOWN",
        source=source,
        target=target,
        material_properties=frozenset(),
    )

    result = evaluate_evidentiary_envelope(envelope)

    assert result["state"] == "UNKNOWN"
    assert result["decision"] == "DEFER"
    assert result["failure"] == "NONE"
    assert result["fail_closed"] is False


def test_fap_adapter_matches_frozen_runtime_for_material_misapplication():
    source = _context()
    target = _context(purpose="litigation-discovery")
    kwargs = {
        "evidence_id": "E-VNEXT-MISAPPLICATION",
        "verification": {"verdict": "STRICT"},
        "source_context": source,
        "target_context": target,
        "transition_id": "T-VNEXT-MISAPPLICATION",
    }

    frozen = assess_fap_transition(**kwargs)
    generic = assess_fap_via_epm_envelope(**kwargs)

    assert _legacy_shape(generic) == frozen
    assert generic["failure"] == "MISAPPLICATION"
    assert generic["decision"] == "QUARANTINE"


def test_fap_adapter_matches_runtime_for_boundary_validated_preservation():
    source = _context()
    target = _context(purpose="litigation-discovery")
    proof = PreservationProof(
        property_name="applicability",
        transition_id="T-VNEXT-PRESERVED",
        rule_id="carrier-default",
        rule_version="1",
        authority="carrier-authority",
        evidence_refs=("E-VNEXT-PRESERVED",),
        valid=True,
        boundary_validated=True,
        source_purpose="claim-verification",
        target_purpose="litigation-discovery",
        source_scope="claim",
        target_scope="claim",
        source_jurisdiction="TX",
        target_jurisdiction="TX",
    )
    kwargs = {
        "evidence_id": "E-VNEXT-PRESERVED",
        "verification": {"verdict": "STRICT"},
        "source_context": source,
        "target_context": target,
        "transition_id": "T-VNEXT-PRESERVED",
        "preservation_proof": proof,
    }

    frozen = assess_fap_transition(**kwargs)
    generic = assess_fap_via_epm_envelope(**kwargs)

    assert _legacy_shape(generic) == frozen
    assert generic["state"] == "PRESERVED"
    assert generic["decision"] == "AUTHORIZED"


def test_fap_adapter_preserves_existing_late_evidence_helper_boundary():
    source = _context()
    target = _context()
    kwargs = {
        "evidence_id": "E-VNEXT-LATE",
        "verification": {
            "verdict": "STRICT",
            "evidence_available_at": AT + timedelta(hours=1),
        },
        "source_context": source,
        "target_context": target,
        "transition_id": "T-VNEXT-LATE",
    }

    frozen = assess_fap_transition(**kwargs)
    generic = assess_fap_via_epm_envelope(**kwargs)

    assert generic == frozen
    assert generic["failure"] == "TEMPORAL_MISMATCH"
    assert generic["fail_closed"] is True


def test_fap_adapter_accepts_only_the_existing_validated_temporal_bridge_rule():
    source = _context()
    target = _context()
    kwargs = {
        "evidence_id": "E-VNEXT-BRIDGED",
        "verification": {
            "verdict": "STRICT",
            "evidence_available_at": AT + timedelta(hours=1),
            "temporal_bridge": {"validated": True, "basis": "trusted external attestation"},
        },
        "source_context": source,
        "target_context": target,
        "transition_id": "T-VNEXT-BRIDGED",
    }

    frozen = assess_fap_transition(**kwargs)
    generic = assess_fap_via_epm_envelope(**kwargs)

    assert _legacy_shape(generic) == frozen
    assert generic["decision"] == "AUTHORIZED"
