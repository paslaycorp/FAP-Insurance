"""Adversarial gate for typed EPM evidence-availability provenance v0.1."""
from datetime import datetime, timedelta, timezone

from epm_temporal import (
    AvailabilityAttestation,
    EvidenceAvailability,
    TemporalAvailability,
    assess_temporal_availability,
)

UTC = timezone.utc
STATE_AT = datetime(2026, 8, 28, 14, 0, tzinfo=UTC)


def _availability(
    *,
    evidence_id: str = "E-AVAIL-1",
    available_at: datetime = STATE_AT,
    observed_at: datetime | None = None,
    validated: bool = True,
    source: str = "trusted-ledger",
    provenance_ref: str = "ledger:record:42",
    basis: str = "signed ingestion record",
) -> EvidenceAvailability:
    return EvidenceAvailability(
        evidence_id=evidence_id,
        available_at=available_at,
        observed_at=observed_at or available_at,
        source=source,
        provenance_ref=provenance_ref,
        attestation=AvailabilityAttestation(
            attestation_id="ATT-42",
            authority="ledger-authority",
            method="signed-ingestion",
            basis=basis,
            validated=validated,
        ),
    )


def test_claimed_event_time_cannot_manufacture_availability():
    claimed_event_time = STATE_AT
    result = assess_temporal_availability(
        evidence_id="E-CLAIMED-TIME",
        state_at=claimed_event_time,
        availability=None,
    )
    assert result.status is TemporalAvailability.UNKNOWN
    assert result.reason_code == "AVAILABILITY_UNKNOWN"
    assert result.trusted is False


def test_processing_time_cannot_manufacture_historical_availability():
    processed_at = STATE_AT + timedelta(hours=2)
    result = assess_temporal_availability(
        evidence_id="E-PROCESSED-TIME",
        state_at=processed_at,
        availability=None,
    )
    assert result.status is TemporalAvailability.UNKNOWN
    assert result.reason_code == "AVAILABILITY_UNKNOWN"


def test_unvalidated_availability_is_not_trusted_temporal_input():
    result = assess_temporal_availability(
        evidence_id="E-AVAIL-1",
        state_at=STATE_AT,
        availability=_availability(validated=False),
    )
    assert result.status is TemporalAvailability.UNKNOWN
    assert result.reason_code == "AVAILABILITY_UNTRUSTED"
    assert result.trusted is False


def test_provenance_free_availability_is_not_trusted_temporal_input():
    result = assess_temporal_availability(
        evidence_id="E-AVAIL-1",
        state_at=STATE_AT,
        availability=_availability(provenance_ref=""),
    )
    assert result.status is TemporalAvailability.UNKNOWN
    assert result.reason_code == "AVAILABILITY_UNTRUSTED"


def test_trusted_late_availability_is_temporally_inadmissible():
    later = STATE_AT + timedelta(minutes=1)
    result = assess_temporal_availability(
        evidence_id="E-AVAIL-1",
        state_at=STATE_AT,
        availability=_availability(available_at=later, observed_at=later),
    )
    assert result.status is TemporalAvailability.UNAVAILABLE
    assert result.reason_code == "EVIDENCE_NOT_YET_AVAILABLE"
    assert result.trusted is True


def test_trusted_prior_availability_is_temporally_admissible():
    earlier = STATE_AT - timedelta(minutes=1)
    result = assess_temporal_availability(
        evidence_id="E-AVAIL-1",
        state_at=STATE_AT,
        availability=_availability(available_at=earlier, observed_at=earlier),
    )
    assert result.status is TemporalAvailability.AVAILABLE
    assert result.reason_code == "EVIDENCE_AVAILABLE"
    assert result.trusted is True
