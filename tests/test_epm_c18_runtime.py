"""Runtime conformance probes for EPM C-18 temporal preservation."""
from datetime import datetime, timezone

import pytest

from dpie_runtime import FAPDecisionContext, assess_fap_transition
from epm import PreservationProof

UTC = timezone.utc


def _context(at: datetime) -> FAPDecisionContext:
    return FAPDecisionContext(
        identity="ADJ-17",
        purpose="claim-adjustment",
        scope="auto",
        jurisdiction="TX",
        at=at,
        rule_id="carrier-default",
        rule_version="1",
        rule_authority="carrier-authority",
        consequence="critical",
    )


def _proof(transition_id: str) -> PreservationProof:
    return PreservationProof(
        property_name="applicability",
        transition_id=transition_id,
        rule_id="carrier-default",
        rule_version="1",
        authority="carrier-authority",
        evidence_refs=("E-C18",),
        valid=True,
        boundary_validated=True,
        source_purpose="claim-adjustment",
        target_purpose="claim-adjustment",
        source_scope="auto",
        target_scope="auto",
        source_jurisdiction="TX",
        target_jurisdiction="TX",
    )


def test_epm_c18_temporal_crossing_without_preservation_fails_closed():
    """A preserved state cannot silently cross a changed temporal context."""
    source_at = datetime(2026, 8, 28, 14, 0, tzinfo=UTC)
    target_at = datetime(2026, 8, 28, 15, 0, tzinfo=UTC)

    result = assess_fap_transition(
        evidence_id="E-C18",
        verification={"verdict": "STRICT"},
        source_context=_context(source_at),
        target_context=_context(target_at),
        transition_id="C18-BLOCKED",
    )

    assert result["state"] == "UNKNOWN"
    assert result["decision"] == "DEFER"
    assert result["failure"] == "NONE"


def test_epm_c18_temporal_crossing_requires_explicit_preservation():
    """A boundary-validated preservation relation permits a material time crossing."""
    source_at = datetime(2026, 8, 28, 14, 0, tzinfo=UTC)
    target_at = datetime(2026, 8, 28, 15, 0, tzinfo=UTC)
    transition_id = "C18-PRESERVED"

    with pytest.raises(ValueError, match="dedicated trusted validation adapter"):
        assess_fap_transition(
            evidence_id="E-C18",
            verification={"verdict": "STRICT"},
            source_context=_context(source_at),
            target_context=_context(target_at),
            transition_id=transition_id,
            preservation_proof=_proof(transition_id),
        )


def test_epm_c18_unchanged_temporal_context_preserves_normal_behavior():
    """No temporal crossing means no preservation proof is required solely for time."""
    at = datetime(2026, 8, 28, 14, 0, tzinfo=UTC)

    result = assess_fap_transition(
        evidence_id="E-C18-CONTROL",
        verification={"verdict": "STRICT"},
        source_context=_context(at),
        target_context=_context(at),
        transition_id="C18-CONTROL",
    )

    assert result["state"] == "UNKNOWN"
    assert result["decision"] == "DEFER"
    assert result["failure"] == "NONE"
