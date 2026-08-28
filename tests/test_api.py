"""FAP-Insurance API contract tests."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from api import app
from config import SETTINGS


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def _headers() -> dict:
    return {SETTINGS.API_KEY_HEADER: SETTINGS.API_KEY}


def _valid_payload(**overrides) -> dict:
    base = {"claim_id": "CLM-2026-004892", "lat": 29.53, "lon": -98.46, "timestamp_claimed": "2026-07-13T22:45:00Z", "device_model": "iPhone15,2", "device_manufacturer": "Apple", "device_os": "iOS 18.4", "witness_ids": ["WIT-001"]}
    base.update(overrides)
    return base


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    assert response.json()["service"] == "fap-insurance"


def test_verify_missing_key(client):
    response = client.post("/verify", json=_valid_payload())
    assert response.status_code == 401
    assert "API key" in response.json().get("detail", "")


def test_verify_invalid_key(client):
    response = client.post("/verify", json=_valid_payload(), headers={SETTINGS.API_KEY_HEADER: "bad-key"})
    assert response.status_code == 403


def test_claim_id_stripped(client):
    response = client.post("/verify", json=_valid_payload(claim_id="  CLM-004892  "), headers=_headers())
    assert response.status_code == 200
    assert response.json()["claim_id"] == "CLM-004892"


def test_claim_id_too_short(client):
    response = client.post("/verify", json=_valid_payload(claim_id="abc"), headers=_headers())
    assert response.status_code == 422
    assert "claim_id" in str(response.json())


def test_media_hash_valid(client):
    response = client.post("/verify", json=_valid_payload(media_hash="E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855"), headers=_headers())
    assert response.status_code == 200


def test_media_hash_wrong_length(client):
    response = client.post("/verify", json=_valid_payload(media_hash="tooshort"), headers=_headers())
    assert response.status_code == 422


def test_media_hash_non_hex(client):
    response = client.post("/verify", json=_valid_payload(media_hash="g3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"), headers=_headers())
    assert response.status_code == 422


def test_future_timestamp_rejected(client):
    future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    response = client.post("/verify", json=_valid_payload(timestamp_claimed=future), headers=_headers())
    assert response.status_code == 422


def test_naive_timestamp_normalized(client):
    response = client.post("/verify", json=_valid_payload(timestamp_claimed="2026-07-13T22:45:00"), headers=_headers())
    assert response.status_code == 200


def test_witness_ids_max_20(client):
    response = client.post("/verify", json=_valid_payload(witness_ids=[f"WIT-{i:03d}" for i in range(21)]), headers=_headers())
    assert response.status_code == 422


def test_witness_ids_blank_rejected(client):
    response = client.post("/verify", json=_valid_payload(witness_ids=["WIT-001", "   ", "WIT-003"]), headers=_headers())
    assert response.status_code == 422


def test_empty_witness_ids_allowed(client):
    response = client.post("/verify", json=_valid_payload(witness_ids=[]), headers=_headers())
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


def test_demo(client):
    response = client.get("/demo")
    assert response.status_code == 200
    assert response.json()["version"] == SETTINGS.VERSION


def test_error_response_has_request_id(client):
    response = client.post("/verify", json=_valid_payload(claim_id="x"), headers=_headers())
    assert response.status_code == 422
    body = response.json()
    assert "error" in body and "detail" in body and "request_id" in body
