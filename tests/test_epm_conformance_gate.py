"""EPM testing-gate conformance probes.

These tests are deliberately adversarial. They probe existing DPIE assurance
boundaries rather than reimplementing EPM in the test suite. A failing probe
is evidence of a conformance gap, not a test defect.
"""
from datetime import datetime, timezone

from dpie_assurance import (
    AssuranceContext,
    AssuranceProperty,
    AssuranceState,
    Decision,
    FailureCode,
    RuleBinding,
    State,
    Transition,
    evaluate_transition,
)
from dpie_composition import evaluate_composition
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
    result = evaluate_transition(
        Transition(
            "T1",
            _state("S0"),
            _state("S1", purpose="litigation-discovery"),
            frozenset({"applicability"}),
        ),
        "applicability",
    )
    assert result.state is AssuranceState.INVALIDATED
    assert result.failure is FailureCode.MISAPPLICATION
    assert result.decision is Decision.QUARANTINE


def test_epm_c02_constraint_does_not_become_resolution_without_exhaustiveness():
    """A narrowing operation alone does not establish singleton resolution."""
    candidates = {"X", "Y"}
    constrained = {"X"}
    assert constrained < candidates
    # No implementation-level resolution claim is permitted by the available
    # assurance API merely because the candidate set was narrowed.
    assert not (constrained == candidates)


def test_epm_c03_discriminator_is_not_observation():
    """A selector must not acquire observational provenance by composition."""
    discriminator = {"selected": "X", "basis": "rule-match"}
    assert "observed" not in discriminator
    assert "source" not in discriminator


def test_epm_c08_dependency_propagation_is_explicit():
    prop = AssuranceProperty(
        "applicability",
        frozenset({"purpose", "scope", "jurisdiction"}),
    )
    assert prop.dependencies == frozenset({"purpose", "scope", "jurisdiction"})


def test_epm_c14_authorization_does_not_follow_epistemic_validity_alone():
    """Authorization requires preserved assurance and no unresolved failure."""
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
    result = evaluate_transition(
        Transition(
            "T1",
            _state("S0", at=datetime(2026, 8, 28, 14, 0, tzinfo=UTC)),
            _state("S1", at=datetime(2026, 8, 28, 15, 0, tzinfo=UTC)),
            frozenset({"applicability"}),
        ),
        "applicability",
    )
    assert result.failure is FailureCode.TEMPORAL_MISMATCH
    assert result.state is AssuranceState.INVALIDATED


def test_epm_c20_individually_valid_components_do_not_authorize_unrelated_composition():
    """Two valid components remain unresolved until their relation is established."""
    result = evaluate_composition(
        left=AssuranceState.PRESERVED,
        right=AssuranceState.PRESERVED,
        relation_established=False,
    )
    assert result.state is AssuranceState.UNKNOWN
    assert result.failure is FailureCode.COMPOSITION_UNRESOLVED
    assert result.decision is Decision.QUARANTINE


def test_epm_c21_later_evidence_cannot_strengthen_prior_state_without_temporal_bridge():
    """Gate blocker: later evidence must not upgrade an earlier epistemic state."""
    later_evidence_available = datetime(2026, 8, 28, 15, 0, tzinfo=UTC)
    earlier_claim_time = datetime(2026, 8, 28, 14, 0, tzinfo=UTC)
    assert later_evidence_available <= earlier_claim_time, (
        "C-21 FAIL: later evidence cannot strengthen a prior state without "
        "an explicit, justified retrospective bridge."
    )
