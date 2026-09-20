from __future__ import annotations

import hashlib
from copy import deepcopy
from datetime import UTC, datetime, timedelta

import pytest

from epm import AvailabilityAttestation, EvidenceAvailability
from epm_fap_trust import (
    EXPECTED_CONTRACT_REVISION_SHA,
    EXPECTED_CONTRACT_VERSION,
    EXPECTED_PRODUCER_REPOSITORY,
    FAPBoundaryValidationError,
    validate_fap_evidence_receipt,
)

NOW = datetime(2026, 9, 20, 9, 45, tzinfo=UTC)
EVIDENCE_ID = "FAP-EV-20260920-ABCDEF12"
PRODUCER_SHA = "a" * 40
PROVENANCE = "provenance:abc123"


def _availability() -> EvidenceAvailability:
    return EvidenceAvailability(
        evidence_id=EVIDENCE_ID,
        available_at=NOW - timedelta(seconds=2),
        observed_at=NOW - timedelta(seconds=1),
        source="fap-insurance-authenticated-request",
        provenance_ref="urn:local:request:1",
        attestation=AvailabilityAttestation(
            attestation_id="local-1",
            authority="FAP-Insurance production API",
            method="authenticated server-side request receipt",
            basis="authenticated ingress",
            validated=True,
        ),
    )


def _receipt() -> dict:
    observed = NOW.isoformat()
    material = (
        f"{EVIDENCE_ID}:{PROVENANCE}:{observed}:"
        f"{PRODUCER_SHA}:{EXPECTED_CONTRACT_VERSION}:{EXPECTED_CONTRACT_REVISION_SHA}"
    )
    receipt_id = "fap-evidence:" + hashlib.sha256(material.encode()).hexdigest()
    return {
        "schema_version": "epm-fap-evidence-receipt/1.0",
        "contract_version": EXPECTED_CONTRACT_VERSION,
        "contract_revision_sha": EXPECTED_CONTRACT_REVISION_SHA,
        "receipt_id": receipt_id,
        "evidence_id": EVIDENCE_ID,
        "source": "fap-core:verify",
        "provenance_ref": PROVENANCE,
        "observed_at": observed,
        "available_at": (NOW - timedelta(seconds=1)).isoformat(),
        "attestation": {
            "attestation_id": f"fap-core-verify:{EVIDENCE_ID}:{PRODUCER_SHA}",
            "authority": "fap-core",
            "method": "verification-pipeline",
            "basis": PROVENANCE,
            "validated": True,
        },
        "boundary_validation": {
            "validated": False,
            "validator": "fap-core",
            "method": "not-evaluated",
            "basis": "producer does not own EPM ingestion trust",
            "validated_at": observed,
        },
        "producer": {
            "component": "fap-core",
            "repository": EXPECTED_PRODUCER_REPOSITORY,
            "commit_sha": PRODUCER_SHA,
        },
    }


def _response(receipt=None) -> dict:
    return {
        "artifact_id": EVIDENCE_ID,
        "verdict": "STRICT",
        "total_score": 0.95,
        "confidence": 0.94,
        "components": {},
        "provenance_hash": PROVENANCE,
        "evidence_receipt": receipt if receipt is not None else _receipt(),
    }


def _runtime() -> dict:
    return {
        "status": "healthy",
        "service": "fap-core",
        "version": "0.2.0",
        "git_commit": PRODUCER_SHA,
        "git_branch": "main",
        "git_repo_slug": EXPECTED_PRODUCER_REPOSITORY,
    }


def _validate(receipt=None, runtime=None, now=NOW):
    response = _response(receipt)
    return validate_fap_evidence_receipt(
        receipt=response["evidence_receipt"],
        fap_response=response,
        runtime_identity=runtime or _runtime(),
        local_availability=_availability(),
        now=now,
    )


def test_canonical_receipt_establishes_only_bound_source_context():
    validated = _validate()

    assert validated.evidence_id == EVIDENCE_ID
    assert validated.producer_commit_sha == PRODUCER_SHA
    assert validated.establishes_source_context(
        evidence_id=EVIDENCE_ID,
        purpose="claim-verification",
        scope="claim",
        jurisdiction="TX",
        rule_id="carrier-default",
        rule_version="1",
        rule_authority="carrier-authority",
    )
    assert not validated.establishes_source_context(
        evidence_id=EVIDENCE_ID,
        purpose="litigation-discovery",
        scope="claim",
        jurisdiction="TX",
        rule_id="carrier-default",
        rule_version="1",
        rule_authority="carrier-authority",
    )


def test_fap_core_cannot_self_assert_boundary_validation():
    hostile = _receipt()
    hostile["boundary_validation"]["validated"] = True
    with pytest.raises(FAPBoundaryValidationError, match="cannot self-assert"):
        _validate(hostile)


def test_wrong_contract_revision_is_rejected():
    hostile = _receipt()
    hostile["contract_revision_sha"] = "b" * 40
    with pytest.raises(FAPBoundaryValidationError, match="wrong EPM contract revision"):
        _validate(hostile)


def test_runtime_sha_must_match_receipt_producer():
    runtime = _runtime()
    runtime["git_commit"] = "b" * 40
    with pytest.raises(FAPBoundaryValidationError, match="does not match observed runtime"):
        _validate(runtime=runtime)


def test_provenance_binding_must_match_fap_response():
    hostile = _receipt()
    hostile["provenance_ref"] = "different"
    with pytest.raises(FAPBoundaryValidationError, match="provenance_ref"):
        _validate(hostile)


def test_receipt_id_tampering_is_rejected():
    hostile = _receipt()
    hostile["receipt_id"] = "fap-evidence:" + "0" * 64
    with pytest.raises(FAPBoundaryValidationError, match="receipt_id integrity"):
        _validate(hostile)


def test_extra_schema_field_is_rejected():
    hostile = _receipt()
    hostile["trust_me"] = True
    with pytest.raises(FAPBoundaryValidationError, match="canonical schema"):
        _validate(hostile)


def test_stale_receipt_is_rejected():
    stale = _receipt()
    old = NOW - timedelta(minutes=10)
    stale["observed_at"] = old.isoformat()
    stale["available_at"] = old.isoformat()
    material = (
        f"{EVIDENCE_ID}:{PROVENANCE}:{stale['observed_at']}:"
        f"{PRODUCER_SHA}:{EXPECTED_CONTRACT_VERSION}:{EXPECTED_CONTRACT_REVISION_SHA}"
    )
    stale["receipt_id"] = "fap-evidence:" + hashlib.sha256(material.encode()).hexdigest()
    with pytest.raises(FAPBoundaryValidationError, match="stale"):
        _validate(stale)
