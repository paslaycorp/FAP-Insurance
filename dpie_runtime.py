"""FAP -> DPIE runtime adapter.

FAP verification remains the evidence source. This adapter constructs a DPIE
source state from that result, constructs the explicitly supplied downstream
state, and evaluates only the assurance-preservation question. It does not
replace FAP verification or grant authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping, Optional

from dpie_assurance import (
    AssuranceContext,
    AssuranceState,
    PreservationProof,
    RuleBinding,
    State,
    Transition,
    evaluate_transition,
)
from dpie_context import RequestAssuranceContext


@dataclass(frozen=True)
class FAPDecisionContext:
    identity: Optional[str]
    purpose: str
    scope: Optional[str]
    jurisdiction: Optional[str]
    at: Optional[datetime]
    rule_id: str
    rule_version: str
    rule_authority: str
    consequence: str = "standard"


def _source_state(evidence_id: str, verification: Mapping[str, Any], context: FAPDecisionContext) -> State:
    verdict = str(verification.get("verdict", "UNKNOWN")).upper()
    source_value = AssuranceState.PRESERVED if verdict in {"STRICT", "PROBABLE"} else AssuranceState.UNKNOWN
    rule = RuleBinding(context.rule_id, context.rule_version, context.rule_authority,
                       context.jurisdiction, context.at)
    return State(
        evidence_id,
        {
            "integrity": source_value,
            "provenance": source_value,
            "evidence": source_value,
            "applicability": source_value,
        },
        AssuranceContext(context.identity, context.purpose, context.scope,
                         context.jurisdiction, context.at),
        rule,
    )


def _proof_from_mapping(raw: Optional[Mapping[str, Any]], transition_id: str) -> Optional[PreservationProof]:
    if not raw:
        return None
    return PreservationProof(
        property_name=str(raw.get("property_name", "applicability")),
        transition_id=str(raw.get("transition_id", transition_id)),
        rule_id=str(raw.get("rule_id", "")),
        rule_version=str(raw.get("rule_version", "")),
        authority=str(raw.get("authority", "")),
        evidence_refs=tuple(str(v) for v in raw.get("evidence_refs", ())),
        valid=bool(raw.get("valid", False)),
        reason=str(raw.get("reason", "")),
        source_purpose=raw.get("source_purpose"),
        target_purpose=raw.get("target_purpose"),
        source_scope=raw.get("source_scope"),
        target_scope=raw.get("target_scope"),
        source_jurisdiction=raw.get("source_jurisdiction"),
        target_jurisdiction=raw.get("target_jurisdiction"),
    )


def assess_fap_transition(*, evidence_id: str, verification: Mapping[str, Any],
                          source_context: FAPDecisionContext,
                          target_context: FAPDecisionContext,
                          transition_id: str,
                          preservation_proof: Any = None) -> Mapping[str, Any]:
    """Evaluate whether FAP assurance may support the target decision."""
    source = _source_state(evidence_id, verification, source_context)
    target_rule = RuleBinding(target_context.rule_id, target_context.rule_version,
                              target_context.rule_authority, target_context.jurisdiction,
                              target_context.at)
    target = State(
        f"{evidence_id}:target",
        {"applicability": AssuranceState.PRESERVED},
        AssuranceContext(target_context.identity, target_context.purpose,
                         target_context.scope, target_context.jurisdiction, target_context.at),
        target_rule,
    )

    proof = preservation_proof
    if isinstance(preservation_proof, Mapping):
        proof = _proof_from_mapping(preservation_proof, transition_id)

    material = any((source_context.purpose != target_context.purpose,
                    source_context.scope != target_context.scope,
                    source_context.jurisdiction != target_context.jurisdiction,
                    source_context.at != target_context.at,
                    source_context.rule_id != target_context.rule_id,
                    source_context.rule_version != target_context.rule_version,
                    source_context.rule_authority != target_context.rule_authority))
    transition = Transition(
        transition_id=transition_id,
        source=source,
        target=target,
        material_properties=frozenset({"applicability"}) if material else frozenset(),
        preservation={"applicability": proof} if proof is not None else {},
    )
    result = evaluate_transition(transition, "applicability", consequence=target_context.consequence)
    return {
        "transition_id": result.transition_id,
        "property": result.property_name,
        "state": result.state.value,
        "decision": result.decision.value,
        "failure": result.failure.value,
        "reason": result.reason,
        "rule_id": result.rule_id,
        "rule_version": result.rule_version,
        "source_evidence_id": evidence_id,
        "fail_closed": result.decision in {"DENY", "QUARANTINE"},
    }


def assess_request_context(*, evidence_id: str, verification: Mapping[str, Any],
                           context: RequestAssuranceContext) -> Mapping[str, Any]:
    source = FAPDecisionContext(
        identity=None,
        purpose=context.source_purpose,
        scope=context.source_scope,
        jurisdiction=context.source_jurisdiction,
        at=context.source_at,
        rule_id=context.rule_id,
        rule_version=context.rule_version,
        rule_authority=context.rule_authority,
        consequence=context.consequence,
    )
    target = FAPDecisionContext(
        identity=None,
        purpose=context.target_purpose,
        scope=context.target_scope,
        jurisdiction=context.target_jurisdiction,
        at=context.target_at,
        rule_id=context.rule_id,
        rule_version=context.rule_version,
        rule_authority=context.rule_authority,
        consequence=context.consequence,
    )
    return assess_fap_transition(
        evidence_id=evidence_id,
        verification=verification,
        source_context=source,
        target_context=target,
        transition_id=f"DPIE-{evidence_id or 'PENDING'}",
        preservation_proof=context.preservation_proof,
    )
