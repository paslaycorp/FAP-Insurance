"""FAP -> EPM runtime adapter with explicit Governor handoff.

The public FAP/DPIE runtime surface is preserved for compatibility. Transition
construction and evaluation now delegate to the generic EPM evidentiary
envelope path so domain-specific callers and generic callers share one semantic
implementation.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from dpie_context import RequestAssuranceContext
from epm_fap_adapter import assess_fap_via_epm_envelope
from epm_fap_semantics import FAPDecisionContext
from epm_fap_trust import ValidatedFAPBoundary


def assess_fap_transition(
    *,
    evidence_id: str,
    verification: Mapping[str, Any],
    source_context: FAPDecisionContext,
    target_context: FAPDecisionContext,
    transition_id: str,
    preservation_proof: Any = None,
    trusted_boundary: ValidatedFAPBoundary | None = None,
) -> Mapping[str, Any]:
    """Compatibility entry point routed through the generic EPM envelope.

    Native EPM evaluation includes a schema version marker. The legacy FAP/DPIE
    surface intentionally removes that additive field so existing callers see
    the exact historical result shape.
    """
    result = dict(
        assess_fap_via_epm_envelope(
            evidence_id=evidence_id,
            verification=verification,
            source_context=source_context,
            target_context=target_context,
            transition_id=transition_id,
            preservation_proof=preservation_proof,
            trusted_boundary=trusted_boundary,
        )
    )
    result.pop("schema_version", None)
    return result


def assess_request_context(
    *,
    evidence_id: str,
    verification: Mapping[str, Any],
    context: RequestAssuranceContext,
    trusted_boundary: ValidatedFAPBoundary | None = None,
) -> Mapping[str, Any]:
    source = FAPDecisionContext(
        None,
        context.source_purpose,
        context.source_scope,
        context.source_jurisdiction,
        context.source_at,
        "carrier-default",
        "1",
        "carrier-authority",
        context.consequence,
    )
    target = FAPDecisionContext(
        None,
        context.target_purpose,
        context.target_scope,
        context.target_jurisdiction,
        context.target_at,
        context.rule_id,
        context.rule_version,
        context.rule_authority,
        context.consequence,
    )
    runtime_verification = dict(verification)
    if context.evidence_availability is not None:
        runtime_verification.setdefault(
            "evidence_availability", context.evidence_availability
        )
    if context.require_trusted_availability:
        runtime_verification["require_trusted_availability"] = True

    return assess_fap_transition(
        evidence_id=evidence_id,
        verification=runtime_verification,
        source_context=source,
        target_context=target,
        transition_id=f"DPIE-{evidence_id or 'PENDING'}",
        preservation_proof=context.preservation_proof,
        trusted_boundary=trusted_boundary,
    )
