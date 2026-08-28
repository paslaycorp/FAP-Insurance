"""DPIE assurance primitives.

FAP establishes evidence. DPIE determines whether an assurance property
established for one state remains entitled to support another state after a
material transition. It does not authenticate artifacts, grant authority, or
make policy decisions outside the explicit transition result.
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
    # Compatibility with the earlier boundary vocabulary.
    VALID = "VALID"


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


class Materiality(str, Enum):
    MATERIAL = "MATERIAL"
    NON_MATERIAL = "NON_MATERIAL"


class Property(str, Enum):
    INTEGRITY = "integrity"
    PROVENANCE = "provenance"
    IDENTITY = "identity"
    EVIDENCE = "evidence"
    APPLICABILITY = "applicability"


@dataclass(frozen=True)
class AssuranceProperty:
    name: str
    dependencies: FrozenSet[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class RuleBinding:
    rule_id: str
    version: str
    authority: str
    jurisdiction: Optional[str] = None
    effective_at: Optional[datetime] = None


@dataclass(frozen=True)
class AssuranceContext:
    identity: Optional[str] = None
    purpose: Optional[str] = None
    scope: Optional[str] = None
    jurisdiction: Optional[str] = None
    at: Optional[datetime] = None


@dataclass(frozen=True)
class State:
    state_id: str
    properties: Mapping[str, AssuranceState]
    context: AssuranceContext
    rule: RuleBinding


@dataclass(frozen=True)
class PreservationProof:
    property_name: str
    transition_id: str = ""
    rule_id: str = ""
    rule_version: str = ""
    authority: str = ""
    evidence_refs: tuple[str, ...] = ()
    valid: bool = True
    reason: str = ""
    # Compatibility alias used by the first boundary tests.
    property: Optional[Property] = None

    def normalized_property_name(self) -> str:
        return self.property_name or (self.property.value if self.property else "")


@dataclass(frozen=True)
class Transition:
    transition_id: str
    source: State
    target: State
    material_properties: FrozenSet[str]
    preservation: Mapping[str, PreservationProof] = field(default_factory=dict)


@dataclass(frozen=True)
class AssuranceTransition:
    """Compatibility adapter for the original boundary-test vocabulary."""
    transition_id: str
    source_state: Mapping[str, object]
    target_state: Mapping[str, object]
    materiality: Materiality
    preservation_proofs: tuple[PreservationProof, ...] = ()


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

    @property
    def reason_code(self) -> str:
        return self.failure.value


def _is_valid_source(value: AssuranceState) -> bool:
    return value in {AssuranceState.PRESERVED, AssuranceState.VALID}


def is_material(transition: Transition, property_name: str) -> bool:
    return property_name in transition.material_properties


def preservation_established(transition: Transition, property_name: str) -> bool:
    proof = transition.preservation.get(property_name)
    if proof is None or not proof.valid:
        return False
    target_rule = transition.target.rule
    proof_property = proof.normalized_property_name()
    if proof_property != property_name:
        return False
    if proof.transition_id != transition.transition_id:
        return False
    if proof.rule_id != target_rule.rule_id or proof.rule_version != target_rule.version:
        return False
    if proof.authority != target_rule.authority or not proof.evidence_refs:
        return False
    # A proof cannot be effective merely because its issuer is named. The
    # target rule's authority is the minimum authority binding here.
    if target_rule.effective_at and transition.target.context.at:
        if target_rule.effective_at > transition.target.context.at:
            return False
    return True


def _result(transition: Transition, property_name: str, state: AssuranceState,
            decision: Decision, failure: FailureCode, reason: str) -> AssuranceResult:
    return AssuranceResult(
        property_name=property_name,
        state=state,
        decision=decision,
        failure=failure,
        reason=reason,
        transition_id=transition.transition_id,
        rule_id=transition.target.rule.rule_id,
        rule_version=transition.target.rule.version,
    )


def evaluate_transition(transition: Transition, property_name: str, *, consequence: str = "standard") -> AssuranceResult:
    source_value = transition.source.properties.get(property_name, AssuranceState.UNKNOWN)
    target_value = transition.target.properties.get(property_name, AssuranceState.UNKNOWN)

    if source_value in {AssuranceState.UNKNOWN, AssuranceState.CONTRADICTED}:
        return _result(transition, property_name, AssuranceState.UNKNOWN, Decision.DEFER,
                       FailureCode.NONE,
                       "Required source assurance is unknown or contradictory; no invalidity is fabricated.")

    if not is_material(transition, property_name):
        if _is_valid_source(source_value):
            return _result(transition, property_name, AssuranceState.PRESERVED,
                           Decision.AUTHORIZED, FailureCode.NONE,
                           "Transition is outside the declared materiality boundary for this property.")
        return _result(transition, property_name, target_value, Decision.DEFER,
                       FailureCode.PRESERVATION_UNESTABLISHED,
                       "Source assurance is not established for this property.")

    if preservation_established(transition, property_name):
        return _result(transition, property_name, AssuranceState.PRESERVED,
                       Decision.AUTHORIZED, FailureCode.NONE,
                       "Explicit preservation relation established for the material transition.")

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

    decision = Decision.DENY if consequence.lower() == "critical" else Decision.QUARANTINE
    return _result(transition, property_name, AssuranceState.INVALIDATED, decision, failure, reason)


def _compat_to_transition(t: AssuranceTransition, property_name: str) -> Transition:
    def convert(raw: Mapping[str, object], default_id: str) -> State:
        props = raw.get("properties", {})
        normalized = {}
        if isinstance(props, Mapping):
            for key, value in props.items():
                normalized[str(getattr(key, "value", key))] = AssuranceState(getattr(value, "value", value))
        context_raw = raw.get("context", {})
        context_raw = context_raw if isinstance(context_raw, Mapping) else {}
        rule_id = str(raw.get("rule_id", "carrier-default"))
        version = str(raw.get("rule_version", "1"))
        authority = str(raw.get("authority_id", "carrier-authority"))
        jurisdiction = context_raw.get("jurisdiction")
        rule = RuleBinding(rule_id, version, authority, str(jurisdiction) if jurisdiction else None)
        return State(
            str(raw.get("state_id", default_id)),
            normalized,
            AssuranceContext(
                identity=str(raw.get("identity")) if raw.get("identity") else None,
                purpose=str(context_raw.get("purpose")) if context_raw.get("purpose") else None,
                scope=str(context_raw.get("scope")) if context_raw.get("scope") else None,
                jurisdiction=str(jurisdiction) if jurisdiction else None,
                at=context_raw.get("at") if isinstance(context_raw.get("at"), datetime) else None,
            ),
            rule,
        )

    source = convert(t.source_state, "Q1")
    target = convert(t.target_state, "Q2")
    proofs = {p.normalized_property_name(): p for p in t.preservation_proofs}
    return Transition(t.transition_id, source, target,
                      frozenset({property_name}) if t.materiality is Materiality.MATERIAL else frozenset(),
                      proofs)


def evaluate_compat_transition(t: AssuranceTransition, property_name: str) -> AssuranceResult:
    return evaluate_transition(_compat_to_transition(t, property_name), property_name,
                               consequence="critical")


# Keep the public function accepting both the canonical Transition and the
# original AssuranceTransition so existing adversarial callers remain valid.
_original_evaluate_transition = evaluate_transition

def evaluate_transition(transition, property_name: str, *, consequence: str = "standard"):
    if isinstance(transition, AssuranceTransition):
        return evaluate_compat_transition(transition, property_name)
    return _original_evaluate_transition(transition, property_name, consequence=consequence)


def perfect_artifact_misapplication_demo() -> AssuranceResult:
    rule = RuleBinding("carrier-default", "1", "carrier-authority", "TX")
    t = datetime(2026, 8, 28, 14, 0, tzinfo=timezone.utc)
    source = State("Q1", {"applicability": AssuranceState.PRESERVED},
                   AssuranceContext("ADJ-17", "claim-adjustment", "auto", "TX", t), rule)
    target = State("Q2", {"applicability": AssuranceState.PRESERVED},
                   AssuranceContext("ADJ-17", "litigation-discovery", "auto", "TX", t), rule)
    return evaluate_transition(Transition("T1", source, target, frozenset({"applicability"})),
                               "applicability", consequence="critical")
