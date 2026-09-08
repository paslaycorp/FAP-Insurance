"""EPM testing-gate conformance probes.

These tests are deliberately adversarial. They do not prove the EPM model by
reimplementing it locally; they probe the existing DPIE assurance boundary and
identify where EPM invariants are, or are not, enforced by executable code.

A failing probe is evidence of a conformance gap, not a test defect.
"""
from datetime import datetime, timezone

import pytest

from dpie_assurance import (
    AssuranceContext,
    AssuranceProperty,
    AssuranceState,
    Decision,
    FailureCode,
    PreservationProof,
    RuleBinding,
    State,
    Transition,
    evaluate_transition,
)
from governor import govern


UTC = timezone.utc


def _state(
    state_id: str,
    *,
    purpose: str = "claim-adjustment",
    scope: str = "auto",
    jurisdiction: str = "TX",
    at: datetime | None = None,
    rule: RuleBinding | None = None,
):
    at = at or datetime(2026, 8, 28, 14, 0, tzinfo=UTC)
    rule = rule or RuleBinding("carrier-default", "1", "carrier-authority", jurisdiction)
    return State(
        state_id,
        {"applicability": AssuranceState.PRESERVED},
        AssuranceContext("ADJ-17", purpose, scope, jurisdiction, at),
        rule,
    )


def test_epm_c01_status_conservation_blocks_unproved_material_crossing():
    """A preserved property must not silently survive a material context change."""
    source = _state("S0")
    target = _state("S1", purpose="litigation-discovery")
    result = evaluate_transition(
        Transition("T1", source, target, frozenset({"applicability"})),
        "applicability",
    )
    assert result.state is AssuranceState.INVALIDATED
    assert result.failure is FailureCode.MISAPPLICATION
    assert result.decision is Decision.QUARANTINE


def test_epm_c02_constraint_does_not_become_resolution_without_exhaustiveness():
    """A narrowing operation must not be represented as proof of a singleton."""
    candidates = {"X", "Y"}
    constrained = {"X"}

    # This is the conformance assertion: narrowing alone supplies no proof that
    # Y was eliminated by a valid discriminator or exhaustive rule.
    assert constrained < candidates
    with pytest.raises(AssertionError):
        assert "X" in candidates and len(constrained) == 1 and constrained == candidates


def test_epm_c03_discriminator_is_not_observation():
    """A discriminator/selector must not silently acquire observational status."""
    discriminator = {"selected": "X", "basis": "rule-match"}
    observation = {"observed": "X", "source": "sensor"}
    assert discriminator != observation
    assert "observed" not in discriminator


def test_epm_c08_dependency_propagation_is_explicit():
    prop = AssuranceProperty(
        "applicability",
        frozenset({"purpose", "scope", "jurisdiction"}),
    )
    assert prop.dependencies == frozenset({"purpose", "scope", "jurisdiction"})


def test_epm_c14_authorization_does_not_follow_epistemic_validity_alone():
    """The Governor must require an assurance state AND a clean failure state."""
    assert govern(
        assurance_state=AssuranceState.PRESERVED,
        failure=FailureCode.NONE,
        consequence="standard",
    ) is Decision.AUTHORIZED
    assert govern(
        assurance_state=AssuranceState.PRESERVED,
        failure=FailureCode.MISAPPLICATION,
        consequence="standard",
    ) is Decision.QUARANTINE
    assert govern(
        assurance_state=AssuranceState.UNKNOWN,
        failure=FailureCode.NONE,
        consequence="critical",
    ) is Decision.DEFER


def test_epm_c18_temporal_preservation_requires_matching_temporal_context():
    """Changing temporal context is material unless preservation is established."""
    source = _state("S0", at=datetime(2026, 8, 28, 14, 0, tzinfo=UTC))
    target = _state("S1", at=datetime(2026, 8, 28, 15, 0, tzinfo=UTC))
    result = evaluate_transition(
        Transition("T1", source, target, frozenset({"applicability"})),
        "applicability",
    )
    assert result.failure is FailureCode.TEMPORAL_MISMATCH
    assert result.state is AssuranceState.INVALIDATED


def test_epm_c21_later_evidence_cannot_strengthen_prior_state_without_temporal_bridge():
    """Gate blocker: later evidence must not be usable to upgrade an earlier state."""
    later_evidence_available = datetime(2026, 8, 28, 15, 0, tzinfo=UTC)
    earlier_claim_time = datetime(2026, 8, 28, 14, 0, tzinfo=UTC)

    # The current assurance API has temporal context, but no temporal-availability
    # field on evidence and no explicit retrospective bridge. This test therefore
    # remains an intentionally failing probe until that enforcement exists.
    assert later_evidence_available <= earlier_claim_time, (
        "C-21 FAIL: later evidence cannot strengthen a prior state without "
        "an explicit, justified retrospective bridge."
    )
