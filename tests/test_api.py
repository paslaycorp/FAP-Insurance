"""
FAP-Insurance — pytest suite
Validators · Auth · Rate limiting · Exception handlers
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

# Must import after sys.path setup if running standalone
from api import app
from config import SETTINGS

client = TestClient(app)


# ═════════════════════════════════════════════════════════════
# Helpers
# ═════════════════════════════════════════════════════════════

def _headers() -> dict:
    return {SETTINGS.API_KEY_HEADER: SETTINGS.API_KEY}


def _valid_payload(**overrides) -> dict:
    base = {
        "claim_id": "CLM-2026-004892",
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


# ═════════════════════════════════════════════════════════════
# Health
# ═════════════════════════════════════════════════════════════

def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["service"] == "fap-insurance"


# ═════════════════════════════════════════════════════════════
# Auth
# ═════════════════════════════════════════════════════════════

def test_verify_missing_key():
    resp = client.post("/verify", json=_valid_payload())
    assert resp.status_code == 401
    assert resp.json()["error"] == "VALIDATION_ERROR" or "API key" in resp.json().get("detail", "")


def test_verify_invalid_key():
    resp = client.post(
        "/verify",
        json=_valid_payload(),
        headers={SETTINGS.API_KEY_HEADER: "bad-key"},
    )
    assert resp.status_code == 403


# ═════════════════════════════════════════════════════════════
# Validators
# ═════════════════════════════════════════════════════════════

def test_claim_id_stripped():
    resp = client.post(
        "/verify",
        json=_valid_payload(claim_id="  CLM-004892  "),
        headers=_headers(),
    )
    assert resp.status_code == 200
    assert resp.json()["claim_id"] == "CLM-004892"


def test_claim_id_too_short():
    resp = client.post(
        "/verify",
        json=_valid_payload(claim_id="abc"),
        headers=_headers(),
    )
    assert resp.status_code == 422
    assert "claim_id" in str(resp.json())


def test_media_hash_valid():
    resp = client.post(
        "/verify",
        json=_valid_payload(
            media_hash="E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855"
        ),
        headers=_headers(),
    )
    assert resp.status_code == 200


def test_media_hash_wrong_length():
    resp = client.post(
        "/verify",
        json=_valid_payload(media_hash="tooshort"),
        headers=_headers(),
    )
    assert resp.status_code == 422


def test_media_hash_non_hex():
    resp = client.post(
        "/verify",
        json=_valid_payload(
            media_hash="g3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        ),
        headers=_headers(),
    )
    assert resp.status_code == 422


def test_future_timestamp_rejected():
    future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    resp = client.post(
        "/verify",
        json=_valid_payload(timestamp_claimed=future),
        headers=_headers(),
    )
    assert resp.status_code == 422


def test_naive_timestamp_normalized():
    resp = client.post(
        "/verify",
        json=_valid_payload(timestamp_claimed="2026-07-13T22:45:00"),
        headers=_headers(),
    )
    assert resp.status_code == 200


def test_witness_ids_max_20():
    resp = client.post(
        "/verify",
        json=_valid_payload(witness_ids=[f"WIT-{i:03d}" for i in range(21)]),
        headers=_headers(),
    )
    assert resp.status_code == 422


def test_witness_ids_blank_rejected():
    resp = client.post(
        "/verify",
        json=_valid_payload(witness_ids=["WIT-001", "   ", "WIT-003"]),
        headers=_headers(),
    )
    assert resp.status_code == 422


def test_empty_witness_ids_allowed():
    resp = client.post(
        "/verify",
        json=_valid_payload(witness_ids=[]),
        headers=_headers(),
    )
    assert resp.status_code == 200


# ═════════════════════════════════════════════════════════════
# Verdict Logic
# ═════════════════════════════════════════════════════════════

def test_verdict_structure():
    resp = client.post("/verify", json=_valid_payload(), headers=_headers())
    assert resp.status_code == 200
    data = resp.json()
    assert data["claim_id"] == "CLM-2026-004892"
    assert data["status"] in ("STRICT", "PROBABLE", "SUSPICIOUS", "QUARANTINE")
    assert 0.0 <= data["score"] <= 1.0
    assert "request_id" in data
    assert "processed_at" in data


# ═════════════════════════════════════════════════════════════
# Demo
# ═════════════════════════════════════════════════════════════

def test_demo():
    resp = client.get("/demo")
    assert resp.status_code == 200
    assert resp.json()["version"] == SETTINGS.VERSION


# ═════════════════════════════════════════════════════════════
# Error Response Shape
# ═════════════════════════════════════════════════════════════

def test_error_response_has_request_id():
    resp = client.post(
        "/verify",
        json=_valid_payload(claim_id="x"),
        headers=_headers(),
    )
    assert resp.status_code == 422
    body = resp.json()
    assert "error" in body
    assert "detail" in body
    assert "request_id" in body
