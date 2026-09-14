"""Bounded in-process observability for EPM decisions in FAP-Insurance.

The registry exposes operational counts and latency only. It does not compute a
truth score or reinterpret EPM assurance semantics.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from datetime import datetime, timezone
from threading import Lock
from typing import Any

from logger import log

_started_at = datetime.now(timezone.utc)
_lock = Lock()
_total = 0
_blocked = 0
_latency_total_ms = 0.0
_latency_max_ms = 0.0
_decisions: Counter[str] = Counter()
_failures: Counter[str] = Counter()
_states: Counter[str] = Counter()
_availability: Counter[str] = Counter()
_source_degradation: Counter[str] = Counter()


def record_epm_decision(
    result: Mapping[str, Any],
    *,
    latency_ms: float,
    availability_status: str,
    fap_core_connected: bool,
) -> None:
    """Record one transition decision and emit a structured operator log."""
    global _total, _blocked, _latency_total_ms, _latency_max_ms

    decision = str(result.get("decision", "UNKNOWN"))
    failure = str(result.get("failure", "UNKNOWN"))
    state = str(result.get("state", "UNKNOWN"))
    latency_ms = max(0.0, float(latency_ms))

    with _lock:
        _total += 1
        if decision in {"DENY", "QUARANTINE", "DEFER"}:
            _blocked += 1
        _latency_total_ms += latency_ms
        _latency_max_ms = max(_latency_max_ms, latency_ms)
        _decisions[decision] += 1
        _failures[failure] += 1
        _states[state] += 1
        _availability[availability_status] += 1
        if not fap_core_connected:
            _source_degradation["FAP-Core"] += 1

    log.info(
        "epm.transition",
        transition_id=result.get("transition_id"),
        source_evidence_id=result.get("source_evidence_id"),
        decision=decision,
        failure=failure,
        assurance_state=state,
        availability_status=availability_status,
        latency_ms=round(latency_ms, 3),
        fap_core_connected=fap_core_connected,
        fail_closed=bool(result.get("fail_closed", False)),
    )


def record_source_degradation(source: str) -> None:
    """Count a degraded evidentiary source without changing its semantics."""
    source = source.strip() or "unknown"
    with _lock:
        _source_degradation[source] += 1
    log.warning("epm.source.degraded", source=source)


def snapshot() -> dict[str, Any]:
    """Return an operator-facing snapshot of the current process."""
    with _lock:
        total = _total
        return {
            "schema_version": "fap.epm-observability/0.1",
            "started_at": _started_at.isoformat(),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "transitions_total": total,
            "fail_closed_total": _blocked,
            "decisions": dict(sorted(_decisions.items())),
            "failures": dict(sorted(_failures.items())),
            "assurance_states": dict(sorted(_states.items())),
            "availability": dict(sorted(_availability.items())),
            "source_degradation": dict(sorted(_source_degradation.items())),
            "latency_ms": {
                "average": round(_latency_total_ms / total, 3) if total else 0.0,
                "max": round(_latency_max_ms, 3),
            },
        }


def reset_for_tests() -> None:
    """Reset counters for deterministic tests only."""
    global _total, _blocked, _latency_total_ms, _latency_max_ms
    with _lock:
        _total = 0
        _blocked = 0
        _latency_total_ms = 0.0
        _latency_max_ms = 0.0
        _decisions.clear()
        _failures.clear()
        _states.clear()
        _availability.clear()
        _source_degradation.clear()
