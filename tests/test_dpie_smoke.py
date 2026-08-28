"""Final smoke checks for the executable assurance boundary."""
from datetime import datetime, timezone

from dpie_assurance import AssuranceContext, AssuranceState, Decision, RuleBinding, State, Transition, evaluate_transition


def test_authentic_verified_state_does_not_authorize_changed_purpose():
    source = State("Q1", {"applicability": AssuranceState.PRESERVED}, AssuranceContext("ADJ-17", "claim-verification", "claim", "TX", datetime(2026, 8, 28, tzinfo=timezone.utc)), RuleBinding("carrier-default", "1", "carrier-authority", "TX"))
    target = State("Q2", {"applicability": AssuranceState.PRESERVED}, AssuranceContext("ADJ-17", "litigation-discovery", "claim", "TX", datetime(2026, 8, 28, tzinfo=timezone.utc)), RuleBinding("carrier-default", "1", "carrier-authority", "TX"))
    result = evaluate_transition(Transition("T-SMOKE", source, target, frozenset({"applicability"})), "applicability", consequence="critical")
    assert result.decision is Decision.DENY
    assert result.failure.value == "MISAPPLICATION"
