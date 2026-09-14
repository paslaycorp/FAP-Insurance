"""Shared FAP -> EPM compatibility semantics.

This module contains only translation logic required to preserve the frozen
FAP/DPIE boundary while routing transition construction through the generic
EPM envelope. It is not a policy engine and does not create new evidence.
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
)


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


def source_state_from_fap(
    evidence_id: str,
    verification: Mapping[str, Any],
    context: FAPDecisionContext,
) -> State:
    verdict = str(verification.get("verdict", "UNKNOWN")).upper()
    value = (
        AssuranceState.PRESERVED
        if verdict in {"STRICT", "PROBABLE"}
        else AssuranceState.UNKNOWN
    )
    return State(
        evidence_id,
        {
            "integrity": value,
            "provenance": value,
            "evidence": value,
            "applicability": value,
        },
        AssuranceContext(
            context.identity,
            context.purpose,
            context.scope,
            context.jurisdiction,
            context.at,
        ),
        RuleBinding(
            context.rule_id,
            context.rule_version,
            context.rule_authority,
            context.jurisdiction,
            context.at,
        ),
    )


def preservation_proof_from_mapping(
    raw: Optional[Mapping[str, Any]],
    transition_id: str,
) -> Optional[PreservationProof]:
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


def validated_temporal_bridge(raw: Any) -> bool:
    return (
        isinstance(raw, Mapping)
        and raw.get("validated") is True
        and isinstance(raw.get("basis"), str)
        and bool(raw["basis"].strip())
    )
