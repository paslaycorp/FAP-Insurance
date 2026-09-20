"""FAP compatibility adapter into the standalone EPM runtime.

FAP owns domain translation only. The generic envelope and transition evaluator
are imported from the frozen standalone EPM RC pinned in requirements.txt.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from epm import (
    AssuranceContext,
    AssuranceState,
    Decision,
    EvidenceAvailability,
    EvidentiaryEnvelope,
    FailureCode,
    PreservationProof,
    RuleBinding,
    State,
    TemporalAvailability,
    assess_temporal_availability,
    assess_transition,
)

from epm_fap_trust import ValidatedFAPBoundary

from epm_fap_semantics import (
    FAPDecisionContext,
    preservation_proof_from_mapping,
    source_state_from_fap,
    validated_temporal_bridge,
)


def envelope_from_fap_transition(
    *,
    evidence_id: str,
    verification: Mapping[str, Any],
    source_context: FAPDecisionContext,
    target_context: FAPDecisionContext,
    transition_id: str,
    preservation_proof: Any = None,
    trusted_boundary: ValidatedFAPBoundary | None = None,
) -> EvidentiaryEnvelope:
    """Translate the existing FAP boundary without semantic promotion."""
    source = source_state_from_fap(
        evidence_id,
        verification,
        source_context,
        trusted_boundary=trusted_boundary,
    )
    target = State(
        f"{evidence_id}:target",
        {"applicability": AssuranceState.UNKNOWN},
        AssuranceContext(
            target_context.identity,
            target_context.purpose,
            target_context.scope,
            target_context.jurisdiction,
            target_context.at,
        ),
        RuleBinding(
            target_context.rule_id,
            target_context.rule_version,
            target_context.rule_authority,
            target_context.jurisdiction,
            target_context.at,
        ),
    )
    if isinstance(preservation_proof, Mapping):
        proof = preservation_proof_from_mapping(preservation_proof, transition_id)
    elif isinstance(preservation_proof, PreservationProof):
        if preservation_proof.boundary_validated:
            raise ValueError(
                "Trusted typed preservation proof is not accepted at the raw FAP "
                "compatibility boundary; use a dedicated trusted validation adapter."
            )
        proof = preservation_proof
    elif preservation_proof is None:
        proof = None
    else:
        raise TypeError("preservation_proof must be a mapping, PreservationProof, or None")
    material = any(
        (
            source_context.purpose != target_context.purpose,
            source_context.scope != target_context.scope,
            source_context.jurisdiction != target_context.jurisdiction,
            source_context.at != target_context.at,
            source_context.rule_id != target_context.rule_id,
            source_context.rule_version != target_context.rule_version,
            source_context.rule_authority != target_context.rule_authority,
        )
    )
    return EvidentiaryEnvelope(
        transition_id=transition_id,
        source=source,
        target=target,
        material_properties=frozenset({"applicability"}) if material else frozenset(),
        preservation={"applicability": proof} if proof is not None else {},
        consequence=target_context.consequence,
    )


def _temporal_result(
    *,
    transition_id: str,
    evidence_id: str,
    target_context: FAPDecisionContext,
    state: AssuranceState,
    decision: Decision,
    reason: str,
) -> Mapping[str, object]:
    return {
        "transition_id": transition_id,
        "property": "applicability",
        "state": state.value,
        "decision": decision.value,
        "failure": FailureCode.TEMPORAL_MISMATCH.value,
        "reason": reason,
        "rule_id": target_context.rule_id,
        "rule_version": target_context.rule_version,
        "source_evidence_id": evidence_id,
        "fail_closed": True,
    }


def assess_fap_via_epm_envelope(
    *,
    evidence_id: str,
    verification: Mapping[str, Any],
    source_context: FAPDecisionContext,
    target_context: FAPDecisionContext,
    transition_id: str,
    preservation_proof: Any = None,
    trusted_boundary: ValidatedFAPBoundary | None = None,
) -> Mapping[str, object]:
    """Evaluate FAP through the standalone EPM package.

    Production callers may require a typed ``EvidenceAvailability`` record. The
    record is assessed against the *target epistemic state time*. This prevents
    evidence first observed later from being silently used in an earlier state.

    The historical ``evidence_available_at`` helper remains compatibility
    behavior for old tests/callers and is not treated as trusted provenance.
    """
    availability = verification.get("evidence_availability")
    require_trusted = verification.get("require_trusted_availability") is True
    if availability is not None or require_trusted:
        trusted_availability = (
            availability if isinstance(availability, EvidenceAvailability) else None
        )
        temporal = assess_temporal_availability(
            evidence_id=evidence_id,
            state_at=target_context.at,
            availability=trusted_availability,
        )
        if temporal.status is TemporalAvailability.UNAVAILABLE:
            decision = (
                Decision.DENY
                if target_context.consequence.lower() == "critical"
                else Decision.QUARANTINE
            )
            return _temporal_result(
                transition_id=transition_id,
                evidence_id=evidence_id,
                target_context=target_context,
                state=AssuranceState.INVALIDATED,
                decision=decision,
                reason=temporal.reason,
            )
        if temporal.status is TemporalAvailability.UNKNOWN and require_trusted:
            return _temporal_result(
                transition_id=transition_id,
                evidence_id=evidence_id,
                target_context=target_context,
                state=AssuranceState.UNKNOWN,
                decision=Decision.DEFER,
                reason=temporal.reason,
            )

    evidence_available_at = verification.get("evidence_available_at")
    temporal_bridge = verification.get("temporal_bridge")
    if (
        isinstance(evidence_available_at, datetime)
        and source_context.at is not None
        and evidence_available_at > source_context.at
        and not validated_temporal_bridge(temporal_bridge)
    ):
        return {
            "transition_id": transition_id,
            "property": "applicability",
            "state": AssuranceState.INVALIDATED.value,
            "decision": (
                Decision.DENY.value
                if target_context.consequence.lower() == "critical"
                else Decision.QUARANTINE.value
            ),
            "failure": FailureCode.TEMPORAL_MISMATCH.value,
            "reason": (
                "Evidence became available after the source temporal context "
                "and no validated temporal bridge was supplied."
            ),
            "rule_id": target_context.rule_id,
            "rule_version": target_context.rule_version,
            "source_evidence_id": evidence_id,
            "fail_closed": True,
        }

    envelope = envelope_from_fap_transition(
        evidence_id=evidence_id,
        verification=verification,
        source_context=source_context,
        target_context=target_context,
        transition_id=transition_id,
        preservation_proof=preservation_proof,
        trusted_boundary=trusted_boundary,
    )
    return assess_transition(envelope)
