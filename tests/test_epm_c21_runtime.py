"""Executable C-21 runtime probes.

These tests exercise the FAP -> DPIE transition adapter rather than asserting
temporal arithmetic in isolation. They deliberately supply temporal provenance
as verification input so the runtime must distinguish claimed event time from
evidence availability time.
"""
from datetime import datetime, timezone

from dpie_runtime import FAPDecisionContext, assess_fap_transition

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


def _valid_preservation_proof(transition_id: str) -> dict:
    return {
        "property_name": "applicability",
        "transition_id": transition_id,
        "rule_id": "carrier-default",
        "rule_version": "1",
        "authority": "carrier-authority",
        "evidence_refs": ["E-C21"],
        "valid": True,
        "source_purpose": "claim-adjustment",
        "target_purpose": "claim-adjustment",
        "source_scope": "auto",
        "target_scope": "auto",
        "source_jurisdiction": "TX",
        "target_jurisdiction": "TX",
    }


def test_epm_c21_runtime_rejects_later_available_evidence_without_temporal_bridge():
    """Later-available evidence must not authorize a prior state merely because
    the ordinary DPIE transition fields otherwise permit preservation.
    """
    claim_time = datetime(2026, 8, 28, 14, 0, tzinfo=UTC)
    later_available = datetime(2026, 8, 28, 15, 0, tzinfo=UTC)
    transition_id = "C21-RUNTIME-LATE"

    result = assess_fap_transition(
        evidence_id="E-C21",
        verification={
            "verdict": "STRICT",
            "evidence_available_at": later_available,
        },
        source_context=_context(claim_time),
        target_context=_context(claim_time),
        transition_id=transition_id,
        preservation_proof=_valid_preservation_proof(transition_id),
    )

    assert result["decision"] != "AUTHORIZED", (
        "C-21 FAIL: later-available evidence received no temporal bridge "
        "but the FAP -> DPIE runtime authorized preservation."
    )


def test_epm_c21_runtime_allows_pre_available_evidence_when_other_preservation_is_valid():
    """Evidence available before the claimed state is not retroactively late."""
    claim_time = datetime(2026, 8, 28, 14, 0, tzinfo=UTC)
    available_before = datetime(2026, 8, 28, 13, 0, tzinfo=UTC)
    transition_id = "C21-RUNTIME-EARLY"

    result = assess_fap_transition(
        evidence_id="E-C21-EARLY",
        verification={
            "verdict": "STRICT",
            "evidence_available_at": available_before,
        },
        source_context=_context(claim_time),
        target_context=_context(claim_time),
        transition_id=transition_id,
        preservation_proof=_valid_preservation_proof(transition_id),
    )

    assert result["decision"] == "AUTHORIZED"
