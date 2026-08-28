"""Runtime adapter connecting FAP evidence results to DPIE assurance decisions.

This module is deliberately framework-agnostic. The HTTP layer should call
`assess_fap_transition` after FAP evidence verification and before a
consequential downstream decision is emitted.

Security property:
    A successful FAP verification is treated as evidence about the source
    state. It is never treated as proof that the same assurance property
    remains applicable after a material context transition.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping, Optional

from dpie_assurance import AssuranceContext, AssuranceState, Decision, RuleBinding, State, Transition, evaluate_transition


@dataclass(frozen=True)
class FAPDecisionContext:
    """Context governing the downstream use of a verified claim."""
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
    """Translate a FAP verification into a DPIE source state."""
    verdict = str(verification.get("verdict", "UNKNOWN")).upper()
    source_value = AssuranceState.VALID if verdict in {"STRICT", "PROBABLE"} else AssuranceState.UNKNOWN
    rule = RuleBinding(context.rule_id, context.rule_version, context.rule_authority, context.jurisdiction, context.at)
    return State(
        evidence_id,
        {"integrity": source_value, "provenance": source_value, "evidence": source_value, "applicability": source_value},
        AssuranceContext(context.identity, context.purpose, context.scope, context.jurisdiction, context.at),
        rule,
    )


def assess_fap_transition(
    *,
    evidence_id: str,
    verification: Mapping[str, Any],
    source_context: FAPDecisionContext,
    target_context: FAPDecisionContext,
    transition_id: str,
    preservation_proof: Any = None,
) -> Mapping[str, Any]:
    """Evaluate whether FAP assurance may support the target decision.

    Omission of a preservation proof is intentionally fail-closed for a
    material applicability transition.
    """
    source = _source_state(evidence_id, verification, source_context)
    target_rule = RuleBinding(
        target_context.rule_id,
        target_context.rule_version,
        target_context.rule_authority,
        target_context.jurisdiction,
        target_context.at,
    )
    target = State(
        f"{evidence_id}:target",
        {"applicability": AssuranceState.PRESERVED},
        AssuranceContext(target_context.identity, target_context.purpose, target_context.scope, target_context.jurisdiction, target_context.at),
        target_rule,
    )
    preservation = {"applicability": preservation_proof} if preservation_proof is not None else {}
    transition = Transition(
        transition_id=transition_id,
        source=source,
        target=target,
        material_properties=frozenset({"applicability"}),
        preservation=preservation,
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
        "fail_closed": result.decision in {Decision.DENY, Decision.QUARANTINE},
    }
