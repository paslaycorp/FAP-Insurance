"""Adversarial tests for production evidence-availability enforcement."""
from datetime import datetime, timedelta, timezone

import pytest

from dpie_context import RequestAssuranceContext
from dpie_runtime import assess_request_context
from epm_fap_availability import (
    FAPAuthenticatedRequestReceipt,
    FAPReceiptIngestionError,
    ingest_fap_authenticated_request,
)


NOW = datetime(2026, 9, 14, 4, 0, tzinfo=timezone.utc)
EVIDENCE_ID = "FAP-EV-C21-PROD"
MEDIA_HASH = "a" * 64


def _receipt(**overrides):
    values = {
        "request_id": "REQ-C21-PROD",
        "evidence_id": EVIDENCE_ID,
        "media_hash": MEDIA_HASH,
        "received_at": NOW,
        "observed_at": NOW + timedelta(milliseconds=5),
        "authenticated": True,
    }
    values.update(overrides)
    return ingest_fap_authenticated_request(
        FAPAuthenticatedRequestReceipt(**values)
    )


def _context(*, target_at=NOW, availability=None, consequence="standard"):
    return RequestAssuranceContext(
        evidence_id=EVIDENCE_ID,
        source_purpose="claim-verification",
        source_scope="claim",
        source_jurisdiction="TX",
        source_at=NOW,
        target_purpose="claim-verification",
        target_scope="claim",
        target_jurisdiction="TX",
        target_at=target_at,
        rule_id="carrier-default",
        rule_version="1",
        rule_authority="carrier-authority",
        consequence=consequence,
        evidence_availability=availability,
        require_trusted_availability=True,
        event_time=NOW - timedelta(days=30),
    )


def test_authenticated_receipt_binds_exact_hash_and_request():
    availability = _receipt()
    assert availability.evidence_id == EVIDENCE_ID
    assert availability.available_at == NOW
    assert MEDIA_HASH in availability.provenance_ref
    assert "REQ-C21-PROD" in availability.provenance_ref
    assert availability.attestation.validated is True


def test_unauthenticated_receipt_is_rejected():
    with pytest.raises(FAPReceiptIngestionError):
        _receipt(authenticated=False)


def test_receipt_rejects_non_sha256_reference():
    with pytest.raises(FAPReceiptIngestionError):
        _receipt(media_hash="not-a-hash")


def test_present_time_receipt_proves_availability_not_assurance_authority():
    availability = _receipt()
    result = assess_request_context(
        evidence_id=EVIDENCE_ID,
        verification={"verdict": "STRICT"},
        context=_context(availability=availability),
    )
    assert result["state"] == "UNKNOWN"
    assert result["decision"] == "DEFER"
    assert result["failure"] == "NONE"


def test_retroactive_target_before_receipt_is_quarantined():
    availability = _receipt()
    result = assess_request_context(
        evidence_id=EVIDENCE_ID,
        verification={"verdict": "STRICT"},
        context=_context(
            availability=availability,
            target_at=NOW - timedelta(seconds=1),
        ),
    )
    assert result["state"] == "INVALIDATED"
    assert result["decision"] == "QUARANTINE"
    assert result["failure"] == "TEMPORAL_MISMATCH"
    assert result["fail_closed"] is True


def test_retroactive_critical_use_is_denied():
    availability = _receipt()
    result = assess_request_context(
        evidence_id=EVIDENCE_ID,
        verification={"verdict": "STRICT"},
        context=_context(
            availability=availability,
            target_at=NOW - timedelta(seconds=1),
            consequence="critical",
        ),
    )
    assert result["decision"] == "DENY"
    assert result["failure"] == "TEMPORAL_MISMATCH"


def test_required_but_missing_availability_defers():
    result = assess_request_context(
        evidence_id=EVIDENCE_ID,
        verification={"verdict": "STRICT"},
        context=_context(availability=None),
    )
    assert result["state"] == "UNKNOWN"
    assert result["decision"] == "DEFER"
    assert result["failure"] == "TEMPORAL_MISMATCH"
    assert result["fail_closed"] is True


def test_capture_event_time_does_not_backdate_epistemic_availability():
    availability = _receipt()
    context = _context(availability=availability)
    assert context.event_time < availability.available_at
    result = assess_request_context(
        evidence_id=EVIDENCE_ID,
        verification={"verdict": "STRICT"},
        context=context,
    )
    assert result["state"] == "UNKNOWN"
    assert result["decision"] == "DEFER"
