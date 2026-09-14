"""Stable public façade for the EPM vNext domain-neutral engine.

The façade intentionally exposes typed assessments rather than a master truth or
confidence score. Domain adapters should depend on this surface rather than on
FAP-specific implementation helpers.
"""
from __future__ import annotations

from collections.abc import Mapping

from epm_envelope import EvidentiaryEnvelope, evaluate_evidentiary_envelope
from epm_state import (
    EvidentiaryState,
    EvidentiaryStateReport,
    inspect_evidentiary_state,
)


EPM_ENGINE_VERSION = "epm-engine/0.1"


def assess_transition(envelope: EvidentiaryEnvelope) -> Mapping[str, object]:
    """Assess whether assurance survives a proposed domain-neutral transition."""
    return evaluate_evidentiary_envelope(envelope)


def inspect_state(state: EvidentiaryState) -> EvidentiaryStateReport:
    """Inspect the typed semantic components of an evidentiary-state snapshot."""
    return inspect_evidentiary_state(state)
