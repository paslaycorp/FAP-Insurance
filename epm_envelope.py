"""Domain-neutral EPM evidentiary transition envelope.

This module intentionally adds no new epistemic subsystem. It packages the
assurance primitives already enforced by the frozen FAP/DPIE boundary so a
domain adapter can hand a transition to EPM without making insurance fields
part of the generic contract.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import FrozenSet, Mapping

from dpie_assurance import Decision, PreservationProof, State, Transition, evaluate_transition
from governor import govern

EPM_ENVELOPE_SCHEMA_VERSION = "epm.evidentiary-envelope/0.1"


@dataclass(frozen=True)
class EvidentiaryEnvelope:
    transition_id: str
    source: State
    target: State
    material_properties: FrozenSet[str]
    preservation: Mapping[str, PreservationProof] = field(default_factory=dict)
    consequence: str = "standard"
    schema_version: str = EPM_ENVELOPE_SCHEMA_VERSION

    def to_transition(self) -> Transition:
        return Transition(
            transition_id=self.transition_id,
            source=self.source,
            target=self.target,
            material_properties=self.material_properties,
            preservation=self.preservation,
        )


def evaluate_evidentiary_envelope(
    envelope: EvidentiaryEnvelope,
    property_name: str = "applicability",
) -> Mapping[str, object]:
    """Evaluate one assurance property without changing source semantics."""
    assurance = evaluate_transition(
        envelope.to_transition(),
        property_name,
        consequence=envelope.consequence,
    )
    decision = govern(
        assurance_state=assurance.state,
        failure=assurance.failure,
        consequence=envelope.consequence,
    )
    return {
        "transition_id": assurance.transition_id,
        "property": assurance.property_name,
        "state": assurance.state.value,
        "decision": decision.value,
        "failure": assurance.failure.value,
        "reason": assurance.reason,
        "rule_id": assurance.rule_id,
        "rule_version": assurance.rule_version,
        "source_evidence_id": envelope.source.state_id,
        "fail_closed": decision in {Decision.DENY, Decision.QUARANTINE},
        "schema_version": envelope.schema_version,
    }
