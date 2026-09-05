from datetime import datetime, timezone

from dpie_context import clear_context, get_context
from models import VerifyClaimRequest


def test_request_model_validation_is_side_effect_free():
    clear_context()
    VerifyClaimRequest(
        claim_id="CLM-2026-004892",
        lat=29.53,
        lon=-98.46,
        timestamp_claimed=datetime(2026, 7, 13, 22, 45, tzinfo=timezone.utc),
        device_model="iPhone15,2",
        device_manufacturer="Apple",
        device_os="iOS 18.4",
    )
    assert get_context() is None


def test_request_model_builds_explicit_assurance_context():
    clear_context()
    request = VerifyClaimRequest(
        claim_id="CLM-2026-004892",
        lat=29.53,
        lon=-98.46,
        timestamp_claimed=datetime(2026, 7, 13, 22, 45, tzinfo=timezone.utc),
        device_model="iPhone15,2",
        device_manufacturer="Apple",
        device_os="iOS 18.4",
        downstream_purpose="litigation-discovery",
        downstream_scope="property",
        downstream_jurisdiction="LA",
        downstream_consequence="critical",
    )
    context = request.dpie_context()
    assert context.target_purpose == "litigation-discovery"
    assert context.target_scope == "property"
    assert context.target_jurisdiction == "LA"
    assert context.consequence == "critical"
    assert get_context() is None
