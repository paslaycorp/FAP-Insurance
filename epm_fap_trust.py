"""Trusted FAP-Core -> EPM boundary validation.

This module is the only compatibility path allowed to turn a canonical
FAP-Core Evidence Receipt into source assurance for the FAP-Insurance EPM
boundary. It does not trust raw payload booleans, FAP scores, verdicts, or
caller-created preservation proofs.
"""
from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from epm import EvidenceAvailability

EXPECTED_SCHEMA_VERSION = "epm-fap-evidence-receipt/1.0"
EXPECTED_CONTRACT_VERSION = "epm-fap-assurance/1.0"
EXPECTED_CONTRACT_REVISION_SHA = "7b20cd45f32c40302388e6cd87c24aa2ab093c5e"
EXPECTED_PRODUCER_COMPONENT = "fap-core"
EXPECTED_PRODUCER_REPOSITORY = "paslaycorp/FAP-Core-v0.2.0"
EXPECTED_RECEIPT_SOURCE = "fap-core:verify"
EXPECTED_ATTESTATION_AUTHORITY = "fap-core"
EXPECTED_ATTESTATION_METHOD = "verification-pipeline"

SOURCE_PURPOSE = "claim-verification"
SOURCE_SCOPE = "claim"
SOURCE_JURISDICTION = "TX"
SOURCE_RULE_ID = "carrier-default"
SOURCE_RULE_VERSION = "1"
SOURCE_RULE_AUTHORITY = "carrier-authority"

VALIDATOR_ID = "fap-insurance:epm-boundary-validator/1"
VALIDATION_METHOD = "canonical-receipt+runtime-identity+local-ingress"
MAX_RECEIPT_AGE = timedelta(minutes=5)
MAX_CLOCK_SKEW = timedelta(seconds=5)
MAX_FUTURE_SKEW = timedelta(seconds=60)
_SHA40 = re.compile(r"^[0-9a-f]{40}$")


class FAPBoundaryValidationError(ValueError):
    """Canonical FAP evidence receipt failed trusted-boundary validation."""


@dataclass(frozen=True, slots=True)
class ValidatedFAPBoundary:
    evidence_id: str
    receipt_id: str
    provenance_ref: str
    producer_commit_sha: str
    contract_revision_sha: str
    validated_at: datetime
    validator: str
    method: str
    basis: str

    def establishes_source_context(
        self,
        *,
        evidence_id: str,
        purpose: str | None,
        scope: str | None,
        jurisdiction: str | None,
        rule_id: str,
        rule_version: str,
        rule_authority: str,
    ) -> bool:
        return all(
            (
                self.evidence_id == evidence_id,
                purpose == SOURCE_PURPOSE,
                scope == SOURCE_SCOPE,
                jurisdiction == SOURCE_JURISDICTION,
                rule_id == SOURCE_RULE_ID,
                rule_version == SOURCE_RULE_VERSION,
                rule_authority == SOURCE_RULE_AUTHORITY,
            )
        )


def _require_mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise FAPBoundaryValidationError(f"{field} must be an object")
    return value


def _require_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise FAPBoundaryValidationError(f"{field} must be a non-empty string")
    return value


def _parse_time(value: Any, field: str) -> datetime:
    text = _require_text(value, field)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise FAPBoundaryValidationError(f"{field} must be RFC3339 date-time") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise FAPBoundaryValidationError(f"{field} must be timezone-aware")
    return parsed


def _require_exact_keys(value: Mapping[str, Any], expected: set[str], field: str) -> None:
    actual = set(value)
    if actual != expected:
        raise FAPBoundaryValidationError(
            f"{field} fields do not match canonical schema: "
            f"missing={sorted(expected - actual)} extra={sorted(actual - expected)}"
        )


def _trusted_local_availability(
    availability: EvidenceAvailability,
    evidence_id: str,
) -> bool:
    attestation = availability.attestation
    if availability.evidence_id != evidence_id:
        return False
    if availability.available_at.tzinfo is None or availability.observed_at.tzinfo is None:
        return False
    if availability.observed_at < availability.available_at:
        return False
    return all(
        (
            bool(availability.source.strip()),
            bool(availability.provenance_ref.strip()),
            bool(attestation.attestation_id.strip()),
            bool(attestation.authority.strip()),
            bool(attestation.method.strip()),
            bool(attestation.basis.strip()),
            attestation.validated is True,
        )
    )


def validate_fap_evidence_receipt(
    *,
    receipt: Mapping[str, Any] | None,
    fap_response: Mapping[str, Any],
    runtime_identity: Mapping[str, Any],
    local_availability: EvidenceAvailability,
    now: datetime | None = None,
) -> ValidatedFAPBoundary:
    """Independently validate a canonical FAP-Core evidence receipt.

    Producer-side boundary validation is never adopted as trust. FAP-Core is
    the evidence producer, not the FAP-Insurance/EPM ingestion authority.
    """
    if receipt is None:
        raise FAPBoundaryValidationError("canonical FAP evidence receipt is missing")
    receipt = _require_mapping(receipt, "receipt")
    response = _require_mapping(fap_response, "fap_response")
    runtime = _require_mapping(runtime_identity, "runtime_identity")

    root_keys = {
        "schema_version",
        "contract_version",
        "contract_revision_sha",
        "receipt_id",
        "evidence_id",
        "source",
        "provenance_ref",
        "observed_at",
        "available_at",
        "attestation",
        "boundary_validation",
        "producer",
    }
    _require_exact_keys(receipt, root_keys, "receipt")

    if receipt["schema_version"] != EXPECTED_SCHEMA_VERSION:
        raise FAPBoundaryValidationError("unexpected receipt schema_version")
    if receipt["contract_version"] != EXPECTED_CONTRACT_VERSION:
        raise FAPBoundaryValidationError("unexpected contract_version")
    if receipt["contract_revision_sha"] != EXPECTED_CONTRACT_REVISION_SHA:
        raise FAPBoundaryValidationError("receipt is bound to the wrong EPM contract revision")

    evidence_id = _require_text(receipt["evidence_id"], "receipt.evidence_id")
    if evidence_id != _require_text(response.get("artifact_id"), "fap_response.artifact_id"):
        raise FAPBoundaryValidationError("receipt evidence_id does not match FAP response")
    if not _trusted_local_availability(local_availability, evidence_id):
        raise FAPBoundaryValidationError("local authenticated evidence availability is not trusted")

    provenance_ref = _require_text(receipt["provenance_ref"], "receipt.provenance_ref")
    if provenance_ref != _require_text(
        response.get("provenance_hash"), "fap_response.provenance_hash"
    ):
        raise FAPBoundaryValidationError("receipt provenance_ref does not match FAP response")
    if receipt["source"] != EXPECTED_RECEIPT_SOURCE:
        raise FAPBoundaryValidationError("unexpected receipt source")

    attestation = _require_mapping(receipt["attestation"], "receipt.attestation")
    _require_exact_keys(
        attestation,
        {"attestation_id", "authority", "method", "basis", "validated"},
        "receipt.attestation",
    )
    _require_text(attestation["attestation_id"], "receipt.attestation.attestation_id")
    if attestation["authority"] != EXPECTED_ATTESTATION_AUTHORITY:
        raise FAPBoundaryValidationError("unexpected FAP attestation authority")
    if attestation["method"] != EXPECTED_ATTESTATION_METHOD:
        raise FAPBoundaryValidationError("unexpected FAP attestation method")
    if attestation["basis"] != provenance_ref:
        raise FAPBoundaryValidationError("attestation basis is not bound to provenance_ref")
    if attestation["validated"] is not True:
        raise FAPBoundaryValidationError("FAP verification attestation is not validated")

    producer_boundary = _require_mapping(
        receipt["boundary_validation"], "receipt.boundary_validation"
    )
    _require_exact_keys(
        producer_boundary,
        {"validated", "validator", "method", "basis", "validated_at"},
        "receipt.boundary_validation",
    )
    if producer_boundary["validated"] is not False:
        raise FAPBoundaryValidationError(
            "FAP-Core cannot self-assert EPM ingestion-boundary validation"
        )
    for field in ("validator", "method", "basis"):
        _require_text(producer_boundary[field], f"receipt.boundary_validation.{field}")
    _parse_time(
        producer_boundary["validated_at"],
        "receipt.boundary_validation.validated_at",
    )

    producer = _require_mapping(receipt["producer"], "receipt.producer")
    _require_exact_keys(
        producer,
        {"component", "repository", "commit_sha"},
        "receipt.producer",
    )
    if producer["component"] != EXPECTED_PRODUCER_COMPONENT:
        raise FAPBoundaryValidationError("unexpected producer component")
    if producer["repository"] != EXPECTED_PRODUCER_REPOSITORY:
        raise FAPBoundaryValidationError("unexpected producer repository")
    producer_sha = _require_text(producer["commit_sha"], "receipt.producer.commit_sha")
    if not _SHA40.fullmatch(producer_sha):
        raise FAPBoundaryValidationError("producer commit is not an exact Git SHA")

    if runtime.get("status") != "healthy" or runtime.get("service") != "fap-core":
        raise FAPBoundaryValidationError("FAP-Core runtime identity is not healthy")
    if runtime.get("git_repo_slug") != EXPECTED_PRODUCER_REPOSITORY:
        raise FAPBoundaryValidationError("runtime repository identity mismatch")
    runtime_sha = _require_text(runtime.get("git_commit"), "runtime_identity.git_commit")
    if not _SHA40.fullmatch(runtime_sha) or runtime_sha != producer_sha:
        raise FAPBoundaryValidationError("receipt producer SHA does not match observed runtime")

    available_at = _parse_time(receipt["available_at"], "receipt.available_at")
    observed_at = _parse_time(receipt["observed_at"], "receipt.observed_at")
    if observed_at < available_at:
        raise FAPBoundaryValidationError("receipt observed_at precedes available_at")
    if available_at + MAX_CLOCK_SKEW < local_availability.available_at:
        raise FAPBoundaryValidationError(
            "FAP-Core availability contradicts earlier local ingress chronology"
        )

    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise FAPBoundaryValidationError("validator clock must be timezone-aware")
    if observed_at > now + MAX_FUTURE_SKEW:
        raise FAPBoundaryValidationError("receipt observation time is implausibly in the future")
    if now - observed_at > MAX_RECEIPT_AGE:
        raise FAPBoundaryValidationError("receipt is stale for live boundary validation")

    receipt_id = _require_text(receipt["receipt_id"], "receipt.receipt_id")
    receipt_material = (
        f"{evidence_id}:{provenance_ref}:{receipt['observed_at']}:"
        f"{producer_sha}:{EXPECTED_CONTRACT_VERSION}:{EXPECTED_CONTRACT_REVISION_SHA}"
    )
    expected_receipt_id = (
        "fap-evidence:" + hashlib.sha256(receipt_material.encode()).hexdigest()
    )
    if receipt_id != expected_receipt_id:
        raise FAPBoundaryValidationError("receipt_id integrity binding failed")

    return ValidatedFAPBoundary(
        evidence_id=evidence_id,
        receipt_id=receipt_id,
        provenance_ref=provenance_ref,
        producer_commit_sha=producer_sha,
        contract_revision_sha=EXPECTED_CONTRACT_REVISION_SHA,
        validated_at=now,
        validator=VALIDATOR_ID,
        method=VALIDATION_METHOD,
        basis=(
            f"validated canonical receipt {receipt_id} from "
            f"{EXPECTED_PRODUCER_REPOSITORY}@{producer_sha} against independently "
            "observed runtime identity and local authenticated ingress provenance"
        ),
    )
