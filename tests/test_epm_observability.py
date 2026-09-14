"""Operator observability tests for EPM decisions."""

from epm_observability import record_epm_decision, reset_for_tests, snapshot


def setup_function():
    reset_for_tests()


def test_observability_counts_decisions_without_truth_score():
    record_epm_decision(
        {
            "transition_id": "T-1",
            "source_evidence_id": "E-1",
            "state": "VALID",
            "decision": "AUTHORIZED",
            "failure": "NONE",
            "fail_closed": False,
        },
        latency_ms=2.5,
        availability_status="AVAILABLE",
        fap_core_connected=True,
    )
    record_epm_decision(
        {
            "transition_id": "T-2",
            "source_evidence_id": "E-2",
            "state": "INVALIDATED",
            "decision": "QUARANTINE",
            "failure": "TEMPORAL_MISMATCH",
            "fail_closed": True,
        },
        latency_ms=7.5,
        availability_status="UNAVAILABLE",
        fap_core_connected=False,
    )

    data = snapshot()
    assert data["transitions_total"] == 2
    assert data["fail_closed_total"] == 1
    assert data["decisions"] == {"AUTHORIZED": 1, "QUARANTINE": 1}
    assert data["failures"]["TEMPORAL_MISMATCH"] == 1
    assert data["availability"] == {"AVAILABLE": 1, "UNAVAILABLE": 1}
    assert data["source_degradation"]["FAP-Core"] == 1
    assert data["latency_ms"]["average"] == 5.0
    assert "score" not in data
    assert "confidence" not in data
