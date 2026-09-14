"""Production evidence-availability connector for FAP-Insurance.

This connector makes one deliberately narrow claim: after API authentication
succeeds, FAP-Insurance can attest that a specific SHA-256 media reference was
present in a request no later than the server receipt time. It does not claim
that the media existed at capture time or at any earlier external time.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re

from epm import AvailabilityAttestation, EvidenceAvailability


class FAPReceiptIngestionError(ValueError):
    """Raised when a production request receipt cannot be trusted."""


@dataclass(frozen=True)
class FAPAuthenticatedRequestReceipt:
    request_id: str
    evidence_id: str
    media_hash: str
    received_at: datetime
    observed_at: datetime
    authenticated: bool


def _aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None


def ingest_fap_authenticated_request(
    receipt: FAPAuthenticatedRequestReceipt,
) -> EvidenceAvailability:
    """Convert an authenticated server receipt into trusted EPM availability.

    The attestation is bounded to *FAP receipt availability*. It proves that the
    evidence reference was observed by this service at ``received_at``. It does
    not backdate availability to ``timestamp_claimed`` or infer media existence
    before the service actually observed the hash.
    """
    request_id = receipt.request_id.strip()
    evidence_id = receipt.evidence_id.strip()
    media_hash = receipt.media_hash.strip().lower()

    if not receipt.authenticated:
        raise FAPReceiptIngestionError("request receipt was not authenticated")
    if not request_id:
        raise FAPReceiptIngestionError("request_id is required")
    if not evidence_id:
        raise FAPReceiptIngestionError("evidence_id is required")
    if len(media_hash) != 64 or not re.fullmatch(r"[0-9a-f]{64}", media_hash):
        raise FAPReceiptIngestionError("media_hash must be a SHA-256 hex digest")
    if not _aware(receipt.received_at) or not _aware(receipt.observed_at):
        raise FAPReceiptIngestionError("receipt times must be timezone-aware")
    if receipt.observed_at < receipt.received_at:
        raise FAPReceiptIngestionError("observed_at cannot precede received_at")

    provenance_ref = (
        f"urn:fap-insurance:request:{request_id}:sha256:{media_hash}"
    )
    attestation = AvailabilityAttestation(
        attestation_id=f"fap-request-receipt:{request_id}",
        authority="FAP-Insurance production API",
        method="authenticated server-side request receipt",
        basis=(
            "FAP-Insurance authenticated the caller and observed this exact "
            "SHA-256 media reference in the request at the recorded receipt time. "
            "This establishes availability to FAP no earlier than that receipt; "
            "it does not establish capture-time existence."
        ),
        validated=True,
    )
    return EvidenceAvailability(
        evidence_id=evidence_id,
        available_at=receipt.received_at,
        observed_at=receipt.observed_at,
        source="fap-insurance-authenticated-request",
        provenance_ref=provenance_ref,
        attestation=attestation,
    )
