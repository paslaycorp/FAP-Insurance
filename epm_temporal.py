"""Typed evidence-availability provenance for EPM vNext.

This module does not infer availability from event, capture, request, or
processing timestamps. It evaluates only an explicitly supplied, provenance-
bearing availability record created by a trusted integration path.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class TemporalAvailability(str, Enum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class AvailabilityAttestation:
    attestation_id: str
    authority: str
    method: str
    basis: str
    validated: bool = False


@dataclass(frozen=True)
class EvidenceAvailability:
    evidence_id: str
    available_at: datetime
    observed_at: datetime
    source: str
    provenance_ref: str
    attestation: AvailabilityAttestation


@dataclass(frozen=True)
class TemporalAvailabilityResult:
    evidence_id: str
    state_at: datetime | None
    status: TemporalAvailability
    trusted: bool
    reason_code: str
    reason: str
    available_at: datetime | None = None
    provenance_ref: str | None = None


def _aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None


def is_trusted_availability(record: EvidenceAvailability, evidence_id: str) -> bool:
    attestation = record.attestation
    return all(
        (
            record.evidence_id == evidence_id,
            _aware(record.available_at),
            _aware(record.observed_at),
            record.observed_at >= record.available_at,
            bool(record.source.strip()),
            bool(record.provenance_ref.strip()),
            bool(attestation.attestation_id.strip()),
            bool(attestation.authority.strip()),
            bool(attestation.method.strip()),
            bool(attestation.basis.strip()),
            attestation.validated is True,
        )
    )


def assess_temporal_availability(
    *,
    evidence_id: str,
    state_at: datetime | None,
    availability: EvidenceAvailability | None,
) -> TemporalAvailabilityResult:
    """Determine whether evidence was available at an epistemic state time.

    Missing or untrusted availability remains UNKNOWN. EPM does not manufacture
    unavailability from absence of evidence and does not manufacture
    availability from unrelated timestamps.
    """
    if availability is None:
        return TemporalAvailabilityResult(
            evidence_id=evidence_id,
            state_at=state_at,
            status=TemporalAvailability.UNKNOWN,
            trusted=False,
            reason_code="AVAILABILITY_UNKNOWN",
            reason="No trusted evidence-availability provenance was supplied.",
        )

    if not is_trusted_availability(availability, evidence_id):
        return TemporalAvailabilityResult(
            evidence_id=evidence_id,
            state_at=state_at,
            status=TemporalAvailability.UNKNOWN,
            trusted=False,
            reason_code="AVAILABILITY_UNTRUSTED",
            reason="The availability assertion lacks the provenance or validated attestation required for trusted temporal use.",
        )

    if state_at is None or not _aware(state_at):
        return TemporalAvailabilityResult(
            evidence_id=evidence_id,
            state_at=state_at,
            status=TemporalAvailability.UNKNOWN,
            trusted=True,
            reason_code="STATE_TIME_UNKNOWN",
            reason="Trusted availability exists, but the epistemic state has no comparable timezone-aware time.",
            available_at=availability.available_at,
            provenance_ref=availability.provenance_ref,
        )

    if availability.available_at > state_at:
        return TemporalAvailabilityResult(
            evidence_id=evidence_id,
            state_at=state_at,
            status=TemporalAvailability.UNAVAILABLE,
            trusted=True,
            reason_code="EVIDENCE_NOT_YET_AVAILABLE",
            reason="Trusted provenance places evidence availability after the epistemic state time.",
            available_at=availability.available_at,
            provenance_ref=availability.provenance_ref,
        )

    return TemporalAvailabilityResult(
        evidence_id=evidence_id,
        state_at=state_at,
        status=TemporalAvailability.AVAILABLE,
        trusted=True,
        reason_code="EVIDENCE_AVAILABLE",
        reason="Trusted provenance places evidence availability on or before the epistemic state time.",
        available_at=availability.available_at,
        provenance_ref=availability.provenance_ref,
    )
