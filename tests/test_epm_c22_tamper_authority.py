"""Executable gate for EPM C-22 provenance-tamper visibility and authority."""

import pytest

import audit


def test_epm_c22_compromised_chain_cannot_serve_authoritative_record(tmp_path):
    """A detected provenance break must block normal authoritative retrieval."""
    audit._db_path = tmp_path / "c22.sqlite3"
    audit._local.conn = None

    record = audit.store_verification(
        request_id="REQ-C22",
        claim_id="CLAIM-C22",
        verdict="STRICT",
        confidence_score=0.95,
        components={"fap_core": 1.0},
        request_payload={"claim_id": "CLAIM-C22", "media_hash": "b" * 64},
        envelope={
            "evidence_id": "FAP-EV-C22",
            "media_hash": "b" * 64,
            "fap_core_response": {"provenance_hash": "PROV-C22"},
        },
        raw_fap_response={"provenance_hash": "PROV-C22"},
    )

    assert audit.get_by_evidence_id(record.evidence_id) is not None

    conn = audit._get_conn()
    conn.execute(
        "UPDATE audit_records SET fap_core_response_json = NULL WHERE evidence_id = ?",
        (record.evidence_id,),
    )
    conn.commit()

    assert audit.get_chain_integrity()["status"] == "compromised"

    with pytest.raises(audit.AuditIntegrityError):
        audit.get_by_evidence_id(record.evidence_id)
