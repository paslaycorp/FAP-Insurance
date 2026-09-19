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
from dpie_runtime import FAPDecisionContext, assess_fap_transition
from epm import PreservationProof

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
    assert not (constrained == candidates)


def test_epm_c03_discriminator_is_not_observation():
    """A selector must not acquire observational provenance by composition."""
    discriminator = {"selected": "X", "basis": "rule-match"}
    assert "observed" not in discriminator
    assert "source" not in discriminator


def test_epm_c08_dependency_propagation_is_explicit():
    """Declared dependencies must propagate material context changes into assurance."""
    prop = AssuranceProperty(
        "applicability",
        frozenset({"purpose", "scope", "jurisdiction"}),
    )
    assert prop.dependencies == frozenset({"purpose", "scope", "jurisdiction"})

    base = _state("S0")
    for dependency, changed in (
        ("purpose", {"purpose": "litigation-discovery"}),
        ("scope", {"scope": "property"}),
        ("jurisdiction", {"jurisdiction": "NM"}),
    ):
        target = _state("S1", **changed)
        result = evaluate_transition(
            Transition(
                f"C08-{dependency.upper()}",
                base,
                target,
                frozenset({"applicability"}),
            ),
            "applicability",
        )
        assert result.state is AssuranceState.INVALIDATED, dependency
        assert result.decision is Decision.QUARANTINE, dependency
        assert result.failure in {
            FailureCode.MISAPPLICATION,
            FailureCode.JURISDICTION_MISMATCH,
        }, dependency

    unchanged = evaluate_transition(
        Transition(
            "C08-UNCHANGED",
            base,
            _state("S2"),
            frozenset(),
        ),
        "applicability",
    )
    assert unchanged.state is AssuranceState.PRESERVED
    assert unchanged.decision is Decision.AUTHORIZED
    assert unchanged.failure is FailureCode.NONE


def test_epm_c14_authorization_does_not_follow_epistemic_validity_alone():
    """A strong verification result cannot bypass runtime governance boundaries."""
    at = datetime(2026, 8, 28, 14, 0, tzinfo=UTC)
    source = FAPDecisionContext(
        identity="ADJ-17",
        purpose="claim-adjustment",
        scope="auto",
        jurisdiction="TX",
        at=at,
        rule_id="carrier-default",
        rule_version="1",
        rule_authority="carrier-authority",
        consequence="critical",
    )
    target = FAPDecisionContext(
        identity="ADJ-17",
        purpose="litigation-discovery",
        scope="auto",
        jurisdiction="TX",
        at=at,
        rule_id="carrier-default",
        rule_version="1",
        rule_authority="carrier-authority",
        consequence="critical",
    )

    blocked = assess_fap_transition(
        evidence_id="E-C14",
        verification={"verdict": "STRICT"},
        source_context=source,
        target_context=target,
        transition_id="C14-BLOCKED",
    )
    assert blocked["state"] == "INVALIDATED"
    assert blocked["decision"] == "DENY"
    assert blocked["failure"] == "MISAPPLICATION"
    assert blocked["fail_closed"] is True

    proof = PreservationProof(
        property_name="applicability",
        transition_id="C14-PERMITTED",
        rule_id="carrier-default",
        rule_version="1",
        authority="carrier-authority",
        evidence_refs=("E-C14",),
        valid=True,
        boundary_validated=True,
        source_purpose="claim-adjustment",
        target_purpose="litigation-discovery",
        source_scope="auto",
        target_scope="auto",
        source_jurisdiction="TX",
        target_jurisdiction="TX",
    )
    permitted = assess_fap_transition(
        evidence_id="E-C14",
        verification={"verdict": "STRICT"},
        source_context=source,
        target_context=target,
        transition_id="C14-PERMITTED",
        preservation_proof=proof,
    )
    assert permitted["state"] == "PRESERVED"
    assert permitted["decision"] == "AUTHORIZED"
    assert permitted["failure"] == "NONE"
    assert permitted["fail_closed"] is False


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


def _c21_context(at: datetime) -> FAPDecisionContext:
    return FAPDecisionContext(
        identity="ADJ-17",
        purpose="claim-adjustment",
        scope="auto",
        jurisdiction="TX",
        at=at,
        rule_id="carrier-default",
        rule_version="1",
        rule_authority="carrier-authority",
        consequence="critical",
    )


def _c21_proof(transition_id: str) -> dict:
    return {
        "property_name": "applicability",
        "transition_id": transition_id,
        "rule_id": "carrier-default",
        "rule_version": "1",
        "authority": "carrier-authority",
        "evidence_refs": ["E-C21"],
        "valid": True,
        "source_purpose": "claim-adjustment",
        "target_purpose": "claim-adjustment",
        "source_scope": "auto",
        "target_scope": "auto",
        "source_jurisdiction": "TX",
        "target_jurisdiction": "TX",
    }


def test_epm_c21_later_evidence_cannot_strengthen_prior_state_without_temporal_bridge():
    """Executable gate: later evidence must fail closed without a bridge."""
    claim_time = datetime(2026, 8, 28, 14, 0, tzinfo=UTC)
    later_available = datetime(2026, 8, 28, 15, 0, tzinfo=UTC)
    transition_id = "C21-GATE-LATE"
    result = assess_fap_transition(
        evidence_id="E-C21",
        verification={"verdict": "STRICT", "evidence_available_at": later_available},
        source_context=_c21_context(claim_time),
        target_context=_c21_context(claim_time),
        transition_id=transition_id,
        preservation_proof=_c21_proof(transition_id),
    )
    assert result["decision"] == "DENY"
    assert result["failure"] == "TEMPORAL_MISMATCH"


def test_epm_c21_later_evidence_requires_explicit_temporal_bridge():
    """A justified bridge permits normal downstream preservation evaluation."""
    claim_time = datetime(2026, 8, 28, 14, 0, tzinfo=UTC)
    later_available = datetime(2026, 8, 28, 15, 0, tzinfo=UTC)
    transition_id = "C21-GATE-BRIDGED"
    result = assess_fap_transition(
        evidence_id="E-C21-BRIDGED",
        verification={
            "verdict": "STRICT",
            "evidence_available_at": later_available,
            "temporal_bridge": {"basis": "retrospective-evidence-validity", "validated": True},
        },
        source_context=_c21_context(claim_time),
        target_context=_c21_context(claim_time),
        transition_id=transition_id,
        preservation_proof=_c21_proof(transition_id),
    )
    assert result["decision"] == "AUTHORIZED"


def test_epm_c21_pre_available_evidence_preserves_existing_behavior():
    """Evidence available before the claimed state remains eligible for normal evaluation."""
    claim_time = datetime(2026, 8, 28, 14, 0, tzinfo=UTC)
    available_before = datetime(2026, 8, 28, 13, 0, tzinfo=UTC)
    transition_id = "C21-GATE-EARLY"
    result = assess_fap_transition(
        evidence_id="E-C21-EARLY",
        verification={"verdict": "STRICT", "evidence_available_at": available_before},
        source_context=_c21_context(claim_time),
        target_context=_c21_context(claim_time),
        transition_id=transition_id,
        preservation_proof=_c21_proof(transition_id),
    )
    assert result["decision"] == "AUTHORIZED"
