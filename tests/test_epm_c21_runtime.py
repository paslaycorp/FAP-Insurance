"""Executable C-21 runtime probes."""
from datetime import datetime, timezone

from dpie_runtime import FAPDecisionContext, assess_fap_transition

UTC = timezone.utc

def _context(at: datetime) -> FAPDecisionContext:
    return FAPDecisionContext("ADJ-17", "claim-adjustment", "auto", "TX", at,
                              "carrier-default", "1", "carrier-authority", "critical")

def _valid_preservation_proof(transition_id: str) -> dict:
    return {"property_name":"applicability","transition_id":transition_id,
            "rule_id":"carrier-default","rule_version":"1","authority":"carrier-authority",
            "evidence_refs":["E-C21"],"valid":True,
            "source_purpose":"claim-adjustment","target_purpose":"claim-adjustment",
            "source_scope":"auto","target_scope":"auto",
            "source_jurisdiction":"TX","target_jurisdiction":"TX"}

def test_epm_c21_runtime_rejects_later_available_evidence_without_temporal_bridge():
    claim_time = datetime(2026,8,28,14,0,tzinfo=UTC)
    later_available = datetime(2026,8,28,15,0,tzinfo=UTC)
    result = assess_fap_transition(
        evidence_id="E-C21",
        verification={"verdict":"STRICT","evidence_available_at":later_available},
        source_context=_context(claim_time), target_context=_context(claim_time),
        transition_id="C21-RUNTIME-LATE",
        preservation_proof=_valid_preservation_proof("C21-RUNTIME-LATE"))
    assert result["decision"] == "DENY"
    assert result["failure"] == "TEMPORAL_MISMATCH"

def test_epm_c21_runtime_allows_later_evidence_with_explicit_temporal_bridge():
    claim_time = datetime(2026,8,28,14,0,tzinfo=UTC)
    later_available = datetime(2026,8,28,15,0,tzinfo=UTC)
    result = assess_fap_transition(
        evidence_id="E-C21-BRIDGED",
        verification={"verdict":"STRICT","evidence_available_at":later_available,
                      "temporal_bridge":{"basis":"retrospective-evidence-validity",
                                         "validated":True}},
        source_context=_context(claim_time), target_context=_context(claim_time),
        transition_id="C21-RUNTIME-BRIDGED",
        preservation_proof=_valid_preservation_proof("C21-RUNTIME-BRIDGED"))
    assert result["decision"] == "AUTHORIZED"

def test_epm_c21_runtime_allows_pre_available_evidence_when_other_preservation_is_valid():
    claim_time = datetime(2026,8,28,14,0,tzinfo=UTC)
    available_before = datetime(2026,8,28,13,0,tzinfo=UTC)
    result = assess_fap_transition(
        evidence_id="E-C21-EARLY",
        verification={"verdict":"STRICT","evidence_available_at":available_before},
        source_context=_context(claim_time), target_context=_context(claim_time),
        transition_id="C21-RUNTIME-EARLY",
        preservation_proof=_valid_preservation_proof("C21-RUNTIME-EARLY"))
    assert result["decision"] == "AUTHORIZED"
