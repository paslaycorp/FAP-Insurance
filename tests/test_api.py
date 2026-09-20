"""FAP-Insurance API contract tests."""
import hashlib
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from api import app
from config import SETTINGS
from epm import EPM_ENGINE_VERSION
from epm_fap_trust import EXPECTED_CONTRACT_REVISION_SHA, EXPECTED_CONTRACT_VERSION


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        producer_sha = "a" * 40

        async def trusted_verify(base_url, payload):
            now = datetime.now(timezone.utc)
            evidence_id = payload["artifact_id"]
            provenance = f"provenance:{evidence_id}"
            observed = now.isoformat()
            material = (
                f"{evidence_id}:{provenance}:{observed}:"
                f"{producer_sha}:{EXPECTED_CONTRACT_VERSION}:{EXPECTED_CONTRACT_REVISION_SHA}"
            )
            receipt_id = "fap-evidence:" + hashlib.sha256(material.encode()).hexdigest()
            return {
                "artifact_id": evidence_id,
                "verdict": "STRICT",
                "total_score": 0.95,
                "confidence": 0.94,
                "components": {"weather": 0.9, "device": 0.9},
                "provenance_hash": provenance,
                "evidence_receipt": {
                    "schema_version": "epm-fap-evidence-receipt/1.0",
                    "contract_version": EXPECTED_CONTRACT_VERSION,
                    "contract_revision_sha": EXPECTED_CONTRACT_REVISION_SHA,
                    "receipt_id": receipt_id,
                    "evidence_id": evidence_id,
                    "source": "fap-core:verify",
                    "provenance_ref": provenance,
                    "observed_at": observed,
                    "available_at": observed,
                    "attestation": {
                        "attestation_id": f"fap-core-verify:{evidence_id}:{producer_sha}",
                        "authority": "fap-core",
                        "method": "verification-pipeline",
                        "basis": provenance,
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
                        "repository": "paslaycorp/FAP-Core-v0.2.0",
                        "commit_sha": producer_sha,
                    },
                },
            }

        async def trusted_runtime_identity(base_url):
            return {
                "status": "healthy",
                "service": "fap-core",
                "version": "0.2.0",
                "git_commit": producer_sha,
                "git_branch": "main",
                "git_repo_slug": "paslaycorp/FAP-Core-v0.2.0",
            }

        async def trusted_health(base_url):
            return True

        test_client.app.state.fap_client.verify = trusted_verify
        test_client.app.state.fap_client.runtime_identity = trusted_runtime_identity
        test_client.app.state.fap_client.health = trusted_health
        yield test_client


def _headers() -> dict:
    return {SETTINGS.API_KEY_HEADER: SETTINGS.API_KEY}


def _valid_payload(**overrides) -> dict:
    base = {
        "claim_id": "CLM-2026-004892",
        "media_hash": "a" * 64,
        "lat": 29.53,
        "lon": -98.46,
        "timestamp_claimed": "2026-07-13T22:45:00Z",
        "device_model": "iPhone15,2",
        "device_manufacturer": "Apple",
        "device_os": "iOS 18.4",
        "witness_ids": ["WIT-001"],
    }
    base.update(overrides)
    return base


def test_live_is_process_liveness_only(client):
    response = client.get("/live")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "fap-insurance"
    assert data["version"] == SETTINGS.VERSION


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "fap-insurance"
    assert data["epm_engine_version"] == EPM_ENGINE_VERSION
    assert "git_commit" in data
    assert "git_branch" in data
    assert "git_repo_slug" in data
    assert "render_service_id" in data
    assert "render_instance_id" in data


def test_verify_missing_key(client):
    response = client.post("/verify", json=_valid_payload())
    assert response.status_code == 401
    assert "API key" in response.json().get("detail", "")


def test_verify_invalid_key(client):
    response = client.post(
        "/verify",
        json=_valid_payload(),
        headers={SETTINGS.API_KEY_HEADER: "bad-key"},
    )
    assert response.status_code == 403


def test_claim_id_stripped(client):
    response = client.post(
        "/verify",
        json=_valid_payload(claim_id="  CLM-004892  "),
        headers=_headers(),
    )
    assert response.status_code == 200
    assert response.json()["claim_id"] == "CLM-004892"


def test_claim_id_too_short(client):
    response = client.post(
        "/verify",
        json=_valid_payload(claim_id="abc"),
        headers=_headers(),
    )
    assert response.status_code == 422
    assert "claim_id" in str(response.json())


def test_media_hash_required_for_production_availability(client):
    response = client.post(
        "/verify",
        json=_valid_payload(media_hash=None),
        headers=_headers(),
    )
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["error"] == "EPM_AVAILABILITY_REQUIRED"


def test_media_hash_valid(client):
    response = client.post(
        "/verify",
        json=_valid_payload(
            media_hash="E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855"
        ),
        headers=_headers(),
    )
    assert response.status_code == 200


def test_media_hash_wrong_length(client):
    response = client.post(
        "/verify",
        json=_valid_payload(media_hash="tooshort"),
        headers=_headers(),
    )
    assert response.status_code == 422


def test_media_hash_non_hex(client):
    response = client.post(
        "/verify",
        json=_valid_payload(
            media_hash="g3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        ),
        headers=_headers(),
    )
    assert response.status_code == 422


def test_future_timestamp_rejected(client):
    future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    response = client.post(
        "/verify",
        json=_valid_payload(timestamp_claimed=future),
        headers=_headers(),
    )
    assert response.status_code == 422


def test_naive_timestamp_normalized(client):
    response = client.post(
        "/verify",
        json=_valid_payload(timestamp_claimed="2026-07-13T22:45:00"),
        headers=_headers(),
    )
    assert response.status_code == 200


def test_witness_ids_max_20(client):
    response = client.post(
        "/verify",
        json=_valid_payload(witness_ids=[f"WIT-{i:03d}" for i in range(21)]),
        headers=_headers(),
    )
    assert response.status_code == 422


def test_witness_ids_blank_rejected(client):
    response = client.post(
        "/verify",
        json=_valid_payload(witness_ids=["WIT-001", "   ", "WIT-003"]),
        headers=_headers(),
    )
    assert response.status_code == 422


def test_empty_witness_ids_allowed(client):
    response = client.post(
        "/verify",
        json=_valid_payload(witness_ids=[]),
        headers=_headers(),
    )
    assert response.status_code == 200


def test_verdict_structure(client):
    response = client.post("/verify", json=_valid_payload(), headers=_headers())
    assert response.status_code == 200
    data = response.json()
    assert data["claim_id"] == "CLM-2026-004892"
    assert data["status"] in ("STRICT", "PROBABLE", "SUSPICIOUS", "QUARANTINE")
    assert 0.0 <= data["score"] <= 1.0
    assert "request_id" in data
    assert "processed_at" in data


def test_epm_metrics_requires_auth(client):
    response = client.get("/epm/metrics")
    assert response.status_code == 401


def test_epm_metrics_operator_surface(client):
    response = client.get("/epm/metrics", headers=_headers())
    assert response.status_code == 200
    data = response.json()
    assert data["schema_version"] == "fap.epm-observability/0.1"
    assert "transitions_total" in data
    assert "decisions" in data
    assert "availability" in data


def test_demo(client):
    response = client.get("/demo")
    assert response.status_code == 200
    assert response.json()["version"] == SETTINGS.VERSION


def test_error_response_has_request_id(client):
    response = client.post(
        "/verify",
        json=_valid_payload(claim_id="x"),
        headers=_headers(),
    )
    assert response.status_code == 422
    body = response.json()
    assert "error" in body and "detail" in body and "request_id" in body


def test_missing_trusted_fap_receipt_blocks_authorization(client):
    original_verify = client.app.state.fap_client.verify

    async def no_receipt(base_url, payload):
        data = await original_verify(base_url, payload)
        data["evidence_receipt"] = None
        return data

    client.app.state.fap_client.verify = no_receipt
    try:
        response = client.post("/verify", json=_valid_payload(), headers=_headers())
        assert response.status_code == 409
        detail = response.json()["detail"]
        assert detail["decision"] == "DEFER"
    finally:
        client.app.state.fap_client.verify = original_verify
