"""Shared FAP -> EPM compatibility semantics.

This module contains only FAP translation logic. The semantic types are owned by
the standalone EPM runtime pinned in requirements.txt.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from epm import (
    AssuranceContext,
    AssuranceState,
    PreservationProof,
    RuleBinding,
    State,
)


@dataclass(frozen=True)
class FAPDecisionContext:
    identity: str | None
    purpose: str
    scope: str | None
    jurisdiction: str | None
    at: datetime | None
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
    raw: Mapping[str, Any] | None,
    transition_id: str,
    *,
    boundary_validated: bool = False,
) -> PreservationProof | None:
    """Translate raw FAP proof data without allowing it to grant itself trust.

    ``boundary_validated`` is an adapter-side trust result, not an input field.
    A raw mapping may contain a ``boundary_validated`` key, but that claim is
    deliberately ignored. Callers may set this keyword only after a legitimate
    ingestion-boundary validation procedure has succeeded.
    """
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
        boundary_validated=boundary_validated,
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
