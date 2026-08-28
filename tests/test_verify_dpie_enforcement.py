"""End-to-end-ish regression test for the /verify processing path.

The external FAP-Core/NOAA dependencies are replaced with deterministic fakes;
the real API processing function, DPIE runtime, EvidenceEnvelope serialization,
and fail-closed decision path are exercised.
"""

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import api
from dpie_context import clear_context
from models import VerifyClaimRequest


class FakeFapClient:
    async def verify(self, _url, _payload):
        return {
            "artifact_id": "FAP-ART-001",
            "verdict": "STRICT",
            "total_score": 0.98,
            "confidence": 0.98,
            "components": {"integrity": 1.0, "provenance": 1.0},
        }


class FakeReality:
    async def check_weather(self, _lat, _lon):
        return {"available": True, "match": 1.0}


class FakeFusion:
    def evaluate(self, _observations):
        return SimpleNamespace(confidence=0.98, verdict="STRICT")


@pytest.mark.asyncio
async def test_verify_material_context_change_is_blocked_and_audited(monkeypatch):
    captured = {}

    async def fake_solar(_timestamp):
        return SimpleNamespace(confidence=1.0, flux=100.0, status="OK", reason=None, to_dict=lambda: {"flux": 100.0})

    def fake_store_verification(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(evidence_id="FAP-EV-AUDIT-001", record_hash="hash-001")

    monkeypatch.setattr(api, "evaluate_solar_correlation", fake_solar)
    monkeypatch.setattr(api, "store_verification", fake_store_verification)

    req = VerifyClaimRequest(
        claim_id="CLM-001",
        media_hash="a" * 64,
        lat=27.8006,
        lon=-97.3964,
        timestamp_claimed=datetime.now(timezone.utc),
        device_model="TestDevice",
        device_manufacturer="TestMaker",
        device_os="TestOS",
        enrollment_id="DEV-001",
        downstream_purpose="litigation",
        downstream_scope="court-evidence",
        downstream_jurisdiction="TX",
        downstream_consequence="critical",
    )

    try:
        with pytest.raises(HTTPException) as exc_info:
            await api._process_single_claim(req, FakeFapClient(), FakeReality(), FakeFusion(), "REQ-001")

        assert exc_info.value.status_code == 403
        detail = exc_info.value.detail
        assert detail["error"] == "DPIE_ASSURANCE_BLOCKED"
        assert detail["decision"] == "DENY"
        assert detail["failure"] == "MISAPPLICATION"
        assert detail["audit_record_hash"] == "hash-001"

        payload = captured["envelope"]
        assert payload["dpie"]["decision"] == "DENY"
        assert payload["dpie"]["failure"] == "MISAPPLICATION"
        assert payload["dpie"]["source_evidence_id"] == payload["evidence_id"]
        assert captured["claim_id"] == "CLM-001"
    finally:
        clear_context()
