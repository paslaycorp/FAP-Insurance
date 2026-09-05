from datetime import datetime, timezone

import pytest

from epm_exchange import (
    AssuranceRequest,
    AttestationSigner,
    BindingError,
    CanonicalizationError,
    ReplayError,
    ReplayGuard,
    SignatureError,
    build_attestation,
    canonical_bytes,
    verify_attestation,
)


NOW = datetime(2026, 9, 5, 20, 0, 0, tzinfo=timezone.utc)


def make_request():
    return AssuranceRequest.create(
        claim_id="CLM-EX-001",
        evidence_id="E-EX-001",
        media_hash="a" * 64,
        timestamp_claimed=NOW,
        purpose="claim-verification",
        scope="claim",
        jurisdiction="TX",
        rule_id="carrier-default",
        rule_version="1",
        authority="carrier-authority",
        consequence="critical",
        requester_service_id="epm-test",
        request_id="4f2b8e2f-5b5a-4b2e-9d6b-7e6d7d7d7d01",
        nonce="N" * 43,
        requested_at=NOW,
    )


def make_attestation(request, signer):
    return build_attestation(
        request,
        artifact_id="ART-001",
        engine_id="fap-core",
        engine_version="0.2.0",
        policy_id="carrier-default",
        policy_version="1",
        oracle_versions=("solar:1", "weather:1"),
        processed_at=NOW,
        result="STRICT",
        confidence=0.9545,
        failure_state=None,
        signer=signer,
    )


def test_request_digest_is_deterministic_and_order_independent():
    request = make_request()
    request.verify_digest()
    a = canonical_bytes({"b": "x", "a": "y"})
    b = canonical_bytes({"a": "y", "b": "x"})
    assert a == b


def test_naive_unordered_collection_is_rejected():
    with pytest.raises(CanonicalizationError):
        canonical_bytes({"items": {"a", "b"}})


def test_signed_attestation_verifies_and_consumes_replay_once():
    request = make_request()
    signer = AttestationSigner.generate("fap-core")
    attestation = make_attestation(request, signer)
    guard = ReplayGuard()
    verify_attestation(
        request,
        attestation,
        trusted_keys={"fap-core": signer.public_key},
        replay_guard=guard,
        expected_engine_id="fap-core",
        expected_engine_version="0.2.0",
        expected_policy_id="carrier-default",
        expected_policy_version="1",
        expected_evidence_id="E-EX-001",
    )
    with pytest.raises(ReplayError):
        verify_attestation(
            request,
            attestation,
            trusted_keys={"fap-core": signer.public_key},
            replay_guard=guard,
        )


def test_tampered_response_field_fails_signature():
    request = make_request()
    signer = AttestationSigner.generate("fap-core")
    attestation = make_attestation(request, signer)
    tampered = attestation.__class__(
        **{**attestation.__dict__, "result": "STRICT-TAMPERED"}
    )
    with pytest.raises(BindingError):
        verify_attestation(
            request,
            tampered,
            trusted_keys={"fap-core": signer.public_key},
            replay_guard=ReplayGuard(),
        )


def test_unknown_responder_identity_fails_closed():
    request = make_request()
    signer = AttestationSigner.generate("fap-core")
    attestation = make_attestation(request, signer)
    with pytest.raises(SignatureError):
        verify_attestation(
            request,
            attestation,
            trusted_keys={},
            replay_guard=ReplayGuard(),
        )


def test_wrong_evidence_cannot_be_attached_to_request():
    request = make_request()
    other = AssuranceRequest.create(
        claim_id="CLM-EX-002",
        evidence_id="E-EX-002",
        media_hash="b" * 64,
        timestamp_claimed=NOW,
        purpose="claim-verification",
        scope="claim",
        jurisdiction="TX",
        rule_id="carrier-default",
        rule_version="1",
        authority="carrier-authority",
        consequence="critical",
        requester_service_id="epm-test",
        request_id="4f2b8e2f-5b5a-4b2e-9d6b-7e6d7d7d7d02",
        nonce="O" * 43,
        requested_at=NOW,
    )
    signer = AttestationSigner.generate("fap-core")
    attestation = make_attestation(other, signer)
    with pytest.raises(BindingError):
        verify_attestation(
            request,
            attestation,
            trusted_keys={"fap-core": signer.public_key},
            replay_guard=ReplayGuard(),
        )


def test_engine_and_policy_identity_are_explicitly_bound():
    request = make_request()
    signer = AttestationSigner.generate("fap-core")
    attestation = make_attestation(request, signer)
    with pytest.raises(BindingError):
        verify_attestation(
            request,
            attestation,
            trusted_keys={"fap-core": signer.public_key},
            replay_guard=ReplayGuard(),
            expected_engine_version="9.9.9",
        )
    with pytest.raises(BindingError):
        verify_attestation(
            request,
            attestation,
            trusted_keys={"fap-core": signer.public_key},
            replay_guard=ReplayGuard(),
            expected_policy_version="9",
        )


def test_request_digest_tampering_is_detected_before_peer_use():
    request = make_request()
    tampered = request.__class__(
        **{**request.__dict__, "purpose": "different-purpose"}
    )
    with pytest.raises(BindingError):
        tampered.verify_digest()


def test_replay_guard_fails_closed_when_capacity_is_exhausted():
    guard = ReplayGuard(max_entries=1)
    guard.accept_once("fap-core", "n1", "d1")
    with pytest.raises(ReplayError):
        guard.accept_once("fap-core", "n2", "d2")
