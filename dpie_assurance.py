"""DPIE assurance primitives and adversarial transition evaluator."""
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
    property_name: str = ""
    transition_id: str = ""
    rule_id: str = ""
    rule_version: str = ""
    authority: str = ""
    evidence_refs: tuple[str, ...] = ()
    valid: bool = True
    reason: str = ""
    property: Optional[Property] = None
    source_purpose: Optional[str] = None
    target_purpose: Optional[str] = None
    source_scope: Optional[str] = None
    target_scope: Optional[str] = None
    source_jurisdiction: Optional[str] = None
    target_jurisdiction: Optional[str] = None

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


def _context_bindings_match(proof: PreservationProof, transition: Transition) -> bool:
    """Require explicit proof binding for every context dimension of a material transition."""
    src, dst = transition.source.context, transition.target.context
    required_bindings = (
        (proof.source_purpose, src.purpose),
        (proof.target_purpose, dst.purpose),
        (proof.source_scope, src.scope),
        (proof.target_scope, dst.scope),
        (proof.source_jurisdiction, src.jurisdiction),
        (proof.target_jurisdiction, dst.jurisdiction),
    )
    return all(declared is not None and declared == actual for declared, actual in required_bindings)


def preservation_established(transition: Transition, property_name: str) -> bool:
    proof = transition.preservation.get(property_name)
    if proof is None or not proof.valid or proof.normalized_property_name() != property_name:
        return False

    rule = transition.target.rule
    if (
        proof.transition_id != transition.transition_id
        or proof.rule_id != rule.rule_id
        or proof.rule_version != rule.version
        or proof.authority != rule.authority
        or not proof.evidence_refs
    ):
        return False

    if rule.effective_at and transition.target.context.at and rule.effective_at > transition.target.context.at:
        return False

    return _context_bindings_match(proof, transition)


def _result(
    t: Transition,
    prop: str,
    state: AssuranceState,
    decision: Decision,
    failure: FailureCode,
    reason: str,
) -> AssuranceResult:
    return AssuranceResult(
        prop,
        state,
        decision,
        failure,
        reason,
        t.transition_id,
        t.target.rule.rule_id,
        t.target.rule.version,
    )


def evaluate_transition(
    transition: Transition,
    property_name: str,
    *,
    consequence: str = "standard",
) -> AssuranceResult:
    source_value = transition.source.properties.get(property_name, AssuranceState.UNKNOWN)
    target_value = transition.target.properties.get(property_name, AssuranceState.UNKNOWN)

    if source_value in {AssuranceState.UNKNOWN, AssuranceState.CONTRADICTED}:
        return _result(
            transition,
            property_name,
            AssuranceState.UNKNOWN,
            Decision.DEFER,
            FailureCode.NONE,
            "Required source assurance is unknown or contradictory; no invalidity is fabricated.",
        )

    if not is_material(transition, property_name):
        if _is_valid_source(source_value):
            return _result(
                transition,
                property_name,
                AssuranceState.PRESERVED,
                Decision.AUTHORIZED,
                FailureCode.NONE,
                "Transition is outside the declared materiality boundary for this property.",
            )
        return _result(
            transition,
            property_name,
            target_value,
            Decision.DEFER,
            FailureCode.PRESERVATION_UNESTABLISHED,
            "Source assurance is not established for this property.",
        )

    proof = transition.preservation.get(property_name)
    if preservation_established(transition, property_name):
        return _result(
            transition,
            property_name,
            AssuranceState.PRESERVED,
            Decision.AUTHORIZED,
            FailureCode.NONE,
            "Explicit preservation relation established for the material transition.",
        )

    src, dst = transition.source.context, transition.target.context
    if proof is not None and proof.valid and proof.authority != transition.target.rule.authority:
        failure, reason = (
            FailureCode.AUTHORITY_MISMATCH,
            "Preservation proof is authentic-looking but was issued by an authority not bound to the target rule.",
        )
    elif src.purpose != dst.purpose or src.scope != dst.scope:
        failure, reason = (
            FailureCode.MISAPPLICATION,
            "Artifact assurance remains intact, but declared application context changed without valid preservation proof.",
        )
    elif src.jurisdiction != dst.jurisdiction:
        failure, reason = (
            FailureCode.JURISDICTION_MISMATCH,
            "Jurisdiction changed without an explicit preservation determination.",
        )
    elif src.at != dst.at:
        failure, reason = (
            FailureCode.TEMPORAL_MISMATCH,
            "Temporal context changed without an explicit preservation determination.",
        )
    elif transition.source.rule != transition.target.rule:
        failure, reason = (
            FailureCode.RULE_MISMATCH,
            "Governing rule binding changed without an explicit preservation determination.",
        )
    elif proof is not None and proof.valid and (
        proof.target_purpose is None or proof.target_purpose != dst.purpose
    ):
        failure, reason = (
            FailureCode.MISAPPLICATION,
            "Preservation proof lacks an explicit binding to the target purpose.",
        )
    elif proof is not None and proof.valid and (
        proof.target_scope is None or proof.target_scope != dst.scope
    ):
        failure, reason = (
            FailureCode.MISAPPLICATION,
            "Preservation proof lacks an explicit binding to the target scope.",
        )
    else:
        failure, reason = (
            FailureCode.PRESERVATION_UNESTABLISHED,
            "Material transition detected, but preservation of the assurance property was not established.",
        )

    decision = Decision.DENY if consequence.lower() == "critical" else Decision.QUARANTINE
    return _result(
        transition,
        property_name,
        AssuranceState.INVALIDATED,
        decision,
        failure,
        reason,
    )


def _compat_to_transition(t: AssuranceTransition, property_name: str) -> Transition:
    def convert(raw: Mapping[str, object], default_id: str) -> State:
        props = raw.get("properties", {})
        normalized = (
            {
                str(getattr(k, "value", k)): AssuranceState(getattr(v, "value", v))
                for k, v in props.items()
            }
            if isinstance(props, Mapping)
            else {}
        )
        if property_name not in normalized:
            normalized[property_name] = (
                AssuranceState.PRESERVED
                if normalized and all(_is_valid_source(v) for v in normalized.values())
                else AssuranceState.UNKNOWN
            )
        c = raw.get("context", {})
        c = c if isinstance(c, Mapping) else {}
        j = c.get("jurisdiction")
        return State(
            str(raw.get("state_id", default_id)),
            normalized,
            AssuranceContext(
                str(raw.get("identity")) if raw.get("identity") else None,
                str(c.get("purpose")) if c.get("purpose") else None,
                str(c.get("scope")) if c.get("scope") else None,
                str(j) if j else None,
                c.get("at") if isinstance(c.get("at"), datetime) else None,
            ),
            RuleBinding(
                str(raw.get("rule_id", "carrier-default")),
                str(raw.get("rule_version", "1")),
                str(raw.get("authority_id", "carrier-authority")),
                str(j) if j else None,
            ),
        )

    source, target = convert(t.source_state, "Q1"), convert(t.target_state, "Q2")
    proofs = {p.normalized_property_name(): p for p in t.preservation_proofs}
    return Transition(
        t.transition_id,
        source,
        target,
        frozenset({property_name}) if t.materiality is Materiality.MATERIAL else frozenset(),
        proofs,
    )


def evaluate_compat_transition(t: AssuranceTransition, property_name: str) -> AssuranceResult:
    return evaluate_transition(_compat_to_transition(t, property_name), property_name, consequence="critical")


_original_evaluate_transition = evaluate_transition


def evaluate_transition(transition, property_name: str, *, consequence: str = "standard"):
    if isinstance(transition, AssuranceTransition):
        return evaluate_compat_transition(transition, property_name)
    return _original_evaluate_transition(transition, property_name, consequence=consequence)


def perfect_artifact_misapplication_demo() -> AssuranceResult:
    rule = RuleBinding("carrier-default", "1", "carrier-authority", "TX")
    t = datetime(2026, 8, 28, 14, 0, tzinfo=timezone.utc)
    source = State(
        "Q1",
        {"applicability": AssuranceState.PRESERVED},
        AssuranceContext("ADJ-17", "claim-adjustment", "auto", "TX", t),
        rule,
    )
    target = State(
        "Q2",
        {"applicability": AssuranceState.PRESERVED},
        AssuranceContext("ADJ-17", "litigation-discovery", "auto", "TX", t),
        rule,
    )
    return evaluate_transition(
        Transition("T1", source, target, frozenset({"applicability"})),
        "applicability",
        consequence="critical",
    )
