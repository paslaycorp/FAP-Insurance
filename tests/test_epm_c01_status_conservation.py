"""Focused executable gate for EPM C-01 epistemic-status conservation."""
from datetime import datetime, timezone

from dpie_assurance import (
    AssuranceContext,
    AssuranceState,
    Decision,
    FailureCode,
    RuleBinding,
    State,
    Transition,
    evaluate_transition,
)

UTC = timezone.utc


def test_epm_c01_target_cannot_promote_changed_source_without_new_evidence():
    """A target declaration cannot upgrade a weaker source state by itself."""
    at = datetime(2026, 8, 28, 14, 0, tzinfo=UTC)
    context = AssuranceContext("ADJ-17", "claim-adjustment", "auto", "TX", at)
    rule = RuleBinding("carrier-default", "1", "carrier-authority", "TX")
    source = State(
        "C01-SOURCE",
        {"applicability": AssuranceState.CHANGED},
        context,
        rule,
    )
    target = State(
        "C01-TARGET",
        {"applicability": AssuranceState.PRESERVED},
        context,
        rule,
    )

    result = evaluate_transition(
        Transition(
            "C01-STATUS-CONSERVATION",
            source,
            target,
            frozenset(),
        ),
        "applicability",
    )

    assert result.state is AssuranceState.CHANGED
    assert result.decision is Decision.DEFER
    assert result.failure is FailureCode.PRESERVATION_UNESTABLISHED
