from datetime import datetime, timezone

import pytest

from dpie_assurance import (
    AssuranceContext,
    AssuranceState,
    Decision,
    FailureCode,
    PreservationProof,
    RuleBinding,
    State,
    Transition,
    evaluate_transition,
)


AT = datetime(2026, 8, 28, 14, 0, tzinfo=timezone.utc)


def _state(state_id: str) -> State:
    rule = RuleBinding("carrier-default", "1", "carrier-authority", "TX")
    return State(
        state_id,
        {"applicability": AssuranceState.PRESERVED},
        AssuranceContext("ADJ-17", "claim-adjustment", "auto", "TX", AT),
        rule,
    )


def _proof(source: State, target: State, **overrides) -> PreservationProof:
    values = dict(
        property_name="applicability",
        transition_id="T-BIND",
        rule_id=target.rule.rule_id,
        rule_version=target.rule.version,
        authority=target.rule.authority,
        evidence_refs=("E1",),
        valid=True,
        source_purpose=source.context.purpose,
        target_purpose=target.context.purpose,
        source_scope=source.context.scope,
        target_scope=target.context.scope,
        source_jurisdiction=source.context.jurisdiction,
        target_jurisdiction=target.context.jurisdiction,
    )
    values.update(overrides)
    return PreservationProof(**values)


@pytest.mark.parametrize(
    "missing_binding",
    (
        "source_purpose",
        "target_purpose",
        "source_scope",
        "target_scope",
        "source_jurisdiction",
        "target_jurisdiction",
    ),
)
def test_material_preservation_requires_every_context_binding(missing_binding):
    source, target = _state("Q1"), _state("Q2")
    transition = Transition(
        "T-BIND",
        source,
        target,
        frozenset({"applicability"}),
        {"applicability": _proof(source, target, **{missing_binding: None})},
    )

    result = evaluate_transition(transition, "applicability")

    assert result.state is AssuranceState.INVALIDATED
    assert result.decision is Decision.QUARANTINE
    assert result.failure is FailureCode.PRESERVATION_UNESTABLISHED


def test_fully_bound_preservation_is_authorized():
    source, target = _state("Q1"), _state("Q2")
    transition = Transition(
        "T-BIND",
        source,
        target,
        frozenset({"applicability"}),
        {"applicability": _proof(source, target)},
    )

    result = evaluate_transition(transition, "applicability")

    assert result.state is AssuranceState.PRESERVED
    assert result.decision is Decision.AUTHORIZED
    assert result.failure is FailureCode.NONE
