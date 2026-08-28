from datetime import datetime, timezone

from dpie_context import RequestAssuranceContext, set_context, clear_context
from evidence import EvidenceEnvelope


def test_dpie_determination_is_embedded_in_existing_audit_payload():
    set_context(RequestAssuranceContext(
        evidence_id=None,
        source_purpose="claim-verification",
        source_scope="claim",
        source_jurisdiction="TX",
        source_at=datetime(2026, 8, 28, tzinfo=timezone.utc),
        target_purpose="litigation-discovery",
        target_scope="claim",
        target_jurisdiction="TX",
        target_at=datetime(2026, 8, 28, tzinfo=timezone.utc),
        rule_id="carrier-default",
        rule_version="1",
        rule_authority="carrier-authority",
        consequence="critical",
    ))
    try:
        envelope = EvidenceEnvelope(
            evidence_id="FAP-EV-TEST-DPIE",
            media_hash="0" * 64,
            capture_time=datetime(2026, 8, 28, tzinfo=timezone.utc),
            latitude=27.8,
            longitude=-97.4,
            confidence_score=0.95,
            verdict="STRICT",
        )
        payload = envelope.to_audit_payload()
        assert payload["dpie"]["failure"] == "MISAPPLICATION"
        assert payload["dpie"]["decision"] == "DENY"
        assert payload["dpie"]["source_evidence_id"] == envelope.evidence_id
        assert payload["dpie"]["source_context"]["purpose"] == "claim-verification"
        assert payload["dpie"]["target_context"]["purpose"] == "litigation-discovery"
    finally:
        clear_context()
