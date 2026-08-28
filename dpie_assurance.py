"""DPIE transition assurance primitives for FAP-Insurance.

This module deliberately does NOT replace evidence verification. It evaluates
whether an assurance property established for one state is entitled to survive
a material transition into another state.

Core invariant:
    P(Q1) does not imply P(Q2) across a material transition unless an
    explicit, authoritative, context-valid preservation relation exists.

The implementation is intentionally dependency-light so it can be embedded
behind the existing FAP verification pipeline without coupling the assurance
model to a particular web framework or database.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import FrozenSet, Mapping, Optional


class AssuranceState(str, Enum):
    PRESERVED = "PRESERVED"
    CHANGED = "CHANGED"
    INVALIDATED = "INVALIDATED"
    UNKNOWN = "UNKNOWN"
    CONTRADICTED = "CONTRADICTED"


class Decision(str, Enum):
    AUTHORIZED = "AUTHORIZED"
    AUTHORIZED_WITH_CONSTRAINTS = "AUTHORIZED_WITH_CONSTRAINTS"
    DEFER = "DEFER"
    QUARANTINE = "QUARANTINE"
    DENY = "DENY"


class FailureCode(str, Enum):
    NONE = "NONE"
    MISAPPLICATION = "MISAPPLICATION"
    AUTHORITY_MISMATCH = "AUTHORITY_MISMATCH"
    JURISDICTION_MISMATCH = "JURISDICTION_MISMATCH"
    TEMPORAL_MISMATCH = "TEMPORAL_MISMATCH"
    RULE_MISMATCH = "RULE_MISMATCH"
    COMPOSITION_UNRESOLVED = "COMPOSITION_UNRESOLVED"
    PRESERVATION_UNESTABLISHED = "PRESERVATION_UNESTABLISHED"
    CONTRADICTORY_EVIDENCE = "CONTRADICTORY_EVIDENCE"


@dataclass(frozen=True)
class AssuranceProperty:
    """A property whose assurance may or may not survive a transition."""

    name: str
    dependencies: FrozenSet[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class RuleBinding:
    """Normative rule identity bound to a determination."""

    rule_id: str
    version: str
    authority: str
    jurisdiction: Optional[str] = None
    effective_at: Optional[datetime] = None


@dataclass(frozen=True)
class AssuranceContext:
    """Context dimensions that may affect applicability."""

    identity: Optional[str] = None
    purpose: Optional[str] = None
    scope: Optional[str] = None
    jurisdiction: Optional[str] = None
    at: Optional[datetime] = None


@dataclass(frozen=True)
class State:
    """Minimal epistemic state used by the transition evaluator."""

    state_id: str
    properties: Mapping[str, AssuranceState]
    context: AssuranceContext
    rule: RuleBinding


@dataclass(frozen=True)
class PreservationProof:
    """Explicit evidence that a property survives a material transition."""

    property_name: str
    transition_id: str
    rule_id: str
    rule_version: str
    authority: str
    evidence_refs: tuple[str, ...]
    valid: bool
    reason: str


@dataclass(frozen=True)
class Transition:
    transition_id: str
    source: State
    target: State
    material_properties: FrozenSet[str]
    preservation: Mapping[str, PreservationProof] = field(default_factory=dict)


@dataclass(frozen=True)
class AssuranceResult:
    property_name: str
    state: AssuranceState
    decision: Decision
    failure: FailureCode
    reason: str
    transition_id: str
    rule_id: str
    rule_version: str


def is_material(transition: Transition, property_name: str) -> bool:
    """Return whether the transition can affect the named property."""

    return property_name in transition.material_properties


def preservation_established(
    transition: Transition,
    property_name: str,
) -> bool:
    """Validate the explicit preservation relation for one property."""

    proof = transition.preservation.get(property_name)
    if proof is None or not proof.valid:
        return False

    target_rule = transition.target.rule
    return (
        proof.transition_id == transition.transition_id
        and proof.property_name == property_name
        and proof.rule_id == target_rule.rule_id
        and proof.rule_version == target_rule.version
        and proof.authority == target_rule.authority
        and bool(proof.evidence_refs)
    )


def evaluate_transition(
    transition: Transition,
    property_name: str,
    *,
    consequence: str = "standard",
) -> AssuranceResult:
    """Evaluate whether an assurance property may cross a transition.

    A material transition without an explicit preservation proof never
    silently inherits the source property's assurance.
    """

    source_value = transition.source.properties.get(property_name, AssuranceState.UNKNOWN)
    target_value = transition.target.properties.get(property_name, AssuranceState.UNKNOWN)

    if not is_material(transition, property_name):
        return AssuranceResult(
            property_name=property_name,
            state=target_value,
            decision=Decision.AUTHORIZED if target_value == AssuranceState.PRESERVED else Decision.DEFER,
            failure=FailureCode.NONE if target_value == AssuranceState.PRESERVED else FailureCode.PRESERVATION_UNESTABLISHED,
            reason="Transition is outside the declared materiality boundary for this property.",
            transition_id=transition.transition_id,
            rule_id=transition.target.rule.rule_id,
            rule_version=transition.target.rule.version,
        )

    if preservation_established(transition, property_name):
        return AssuranceResult(
            property_name=property_name,
            state=AssuranceState.PRESERVED,
            decision=Decision.AUTHORIZED,
            failure=FailureCode.NONE,
            reason="Explicit preservation relation established for the material transition.",
            transition_id=transition.transition_id,
            rule_id=transition.target.rule.rule_id,
            rule_version=transition.target.rule.version,
        )

    # Context changes are deliberately classified separately from tampering.
    src = transition.source.context
    dst = transition.target.context
    if src.purpose != dst.purpose or src.scope != dst.scope:
        failure = FailureCode.MISAPPLICATION
        reason = "Artifact assurance remains intact, but declared application context changed without preservation proof."
    elif src.jurisdiction != dst.jurisdiction:
        failure = FailureCode.JURISDICTION_MISMATCH
        reason = "Jurisdiction changed without an explicit preservation determination."
    elif src.at != dst.at:
        failure = FailureCode.TEMPORAL_MISMATCH
        reason = "Temporal context changed without an explicit preservation determination."
    elif transition.source.rule != transition.target.rule:
        failure = FailureCode.RULE_MISMATCH
        reason = "Governing rule binding changed without an explicit preservation determination."
    else:
        failure = FailureCode.PRESERVATION_UNESTABLISHED
        reason = "Material transition detected, but preservation of the assurance property was not established."

    decision = Decision.DENY if consequence == "critical" else Decision.QUARANTINE
    return AssuranceResult(
        property_name=property_name,
        state=AssuranceState.INVALIDATED,
        decision=decision,
        failure=failure,
        reason=reason,
        transition_id=transition.transition_id,
        rule_id=transition.target.rule.rule_id,
        rule_version=transition.target.rule.version,
    )


def perfect_artifact_misapplication_demo() -> AssuranceResult:
    """Canonical DPIE adversarial case: perfect evidence, changed purpose."""

    rule = RuleBinding("carrier-default", "1", "carrier-authority", "TX")
    t = datetime(2026, 8, 28, 14, 0, tzinfo=timezone.utc)
    source = State(
        "Q1",
        {"applicability": AssuranceState.PRESERVED},
        AssuranceContext(identity="ADJ-17", purpose="claim-adjustment", scope="auto", jurisdiction="TX", at=t),
        rule,
    )
    target = State(
        "Q2",
        {"applicability": AssuranceState.PRESERVED},
        AssuranceContext(identity="ADJ-17", purpose="litigation-discovery", scope="auto", jurisdiction="TX", at=t),
        rule,
    )
    transition = Transition("T1", source, target, frozenset({"applicability"}))
    return evaluate_transition(transition, "applicability", consequence="critical")
