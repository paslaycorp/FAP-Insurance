"""Compatibility adapter from the current FAP runtime into the generic EPM envelope.

The adapter preserves the frozen FAP/DPIE semantics. It does not change the
production request model and it does not treat claimed/capture/processed time
as evidence-availability provenance.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from dpie_assurance import AssuranceContext, AssuranceState, Decision, FailureCode, RuleBinding, State
from dpie_runtime import (
    FAPDecisionContext,
    _proof_from_mapping,
    _source_state,
    _validated_temporal_bridge,
)
from epm_envelope import EvidentiaryEnvelope, evaluate_evidentiary_envelope


def envelope_from_fap_transition(
    *,
    evidence_id: str,
    verification: Mapping[str, Any],
    source_context: FAPDecisionContext,
    target_context: FAPDecisionContext,
    transition_id: str,
    preservation_proof: Any = None,
) -> EvidentiaryEnvelope:
    """Translate the existing FAP/DPIE transition inputs without semantic promotion."""
    source = _source_state(evidence_id, verification, source_context)
    target = State(
        f"{evidence_id}:target",
        {"applicability": AssuranceState.PRESERVED},
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
    proof = (
        _proof_from_mapping(preservation_proof, transition_id)
        if isinstance(preservation_proof, Mapping)
        else preservation_proof
    )
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


def assess_fap_via_epm_envelope(
    *,
    evidence_id: str,
    verification: Mapping[str, Any],
    source_context: FAPDecisionContext,
    target_context: FAPDecisionContext,
    transition_id: str,
    preservation_proof: Any = None,
) -> Mapping[str, object]:
    """Compatibility evaluator used only for vNext parity testing.

    The current C-21 helper remains outside the generic envelope until trusted
    evidence-availability provenance is modeled end to end.
    """
    evidence_available_at = verification.get("evidence_available_at")
    temporal_bridge = verification.get("temporal_bridge")
    if (
        isinstance(evidence_available_at, datetime)
        and source_context.at is not None
        and evidence_available_at > source_context.at
        and not _validated_temporal_bridge(temporal_bridge)
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
    )
    return evaluate_evidentiary_envelope(envelope)
