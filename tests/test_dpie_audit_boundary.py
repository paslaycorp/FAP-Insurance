from datetime import datetime, timezone

import audit
from dpie_context import RequestAssuranceContext, clear_context, set_context
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
        assert payload["dpie"]["failure"] == "NONE"
        assert payload["dpie"]["decision"] == "DEFER"
        assert payload["dpie"]["source_evidence_id"] == envelope.evidence_id
        assert payload["dpie"]["source_context"]["purpose"] == "claim-verification"
        assert payload["dpie"]["target_context"]["purpose"] == "litigation-discovery"
    finally:
        clear_context()


def test_epm_c02_broken_provenance_dependency_is_detected_by_audit_chain(tmp_path):
    """Breaking a stored upstream provenance dependency must surface as compromised."""
    audit._db_path = tmp_path / "c02.sqlite3"
    record = audit.store_verification(
        request_id="REQ-C02",
        claim_id="CLAIM-C02",
        verdict="STRICT",
        confidence_score=0.95,
        components={"fap_core": 1.0},
        request_payload={"claim_id": "CLAIM-C02", "media_hash": "a" * 64},
        envelope={
            "evidence_id": "FAP-EV-C02",
            "media_hash": "a" * 64,
            "fap_core_response": {"provenance_hash": "PROV-C02"},
        },
        raw_fap_response={"provenance_hash": "PROV-C02"},
    )

    assert audit.get_chain_integrity()["status"] == "intact"

    conn = audit._get_conn()
    conn.execute(
        "UPDATE audit_records SET fap_core_response_json = NULL WHERE evidence_id = ?",
        (record.evidence_id,),
    )
    conn.commit()

    integrity = audit.get_chain_integrity()
    assert integrity["status"] == "compromised"
    assert integrity["breaks"]
    assert integrity["breaks"][0]["evidence_id"] == record.evidence_id
