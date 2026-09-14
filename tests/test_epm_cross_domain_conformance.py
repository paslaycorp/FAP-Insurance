"""Cross-domain adversarial conformance gate for the generic EPM vNext engine.

These cases deliberately bypass VerifyClaimRequest and insurance-specific input
models. The same invariants must survive arbitrary domain context labels.
"""
from datetime import datetime, timezone

import pytest

from dpie_assurance import AssuranceContext, AssuranceState, RuleBinding, State
from epm_constraints import Constraint, EntailmentStatus, PremiseState
from epm_engine import assess_transition
from epm_envelope import EvidentiaryEnvelope
from epm_justification import (
    JustificationGraph,
    JustificationNode,
    JustificationNodeType,
    SupportEdge,
    SupportRelation,
    detect_cycle,
)
from epm_resolution import EpistemicStanding, ResolutionState, create_answer_space, recompute_with_constraints
from epm_sources import EpistemicSourceRecord, EpistemicSourceType, observation_reclassification_allowed
from epm_temporal import TemporalAvailability, assess_temporal_availability

UTC = timezone.utc
AT = datetime(2026, 9, 13, 18, 0, tzinfo=UTC)

DOMAINS = (
    ("insurance", "claim-verification", "claim", "US-TX", "carrier-rule", "carrier-authority"),
    ("legal", "evidence-admission", "civil-case-record", "US-TX-COURT", "rules-of-evidence", "court-authority"),
    ("scientific", "hypothesis-testing", "experiment-A", "LAB-PROTOCOL", "protocol-17", "research-governance"),
    ("machine-analysis", "analytical-support", "dataset-A", "ENTERPRISE", "analysis-policy", "model-risk-board"),
    ("financial", "credit-decision-support", "application", "US", "lending-policy", "risk-authority"),
    ("compliance", "regulatory-review", "filing", "US", "compliance-rule", "compliance-authority"),
    ("intelligence", "analytical-assessment", "case-file", "MISSION-A", "analytic-standard", "analytic-authority"),
)


def _states(domain):
    name, purpose, scope, jurisdiction, rule_id, authority = domain
    rule = RuleBinding(rule_id, "1", authority, jurisdiction, AT)
    context = AssuranceContext(f"actor:{name}", purpose, scope, jurisdiction, AT)
    source = State(
        f"{name}:source",
        {"applicability": AssuranceState.PRESERVED},
        context,
        rule,
    )
    target_context = AssuranceContext(
        f"actor:{name}",
        f"{purpose}:secondary-use",
        scope,
        jurisdiction,
        AT,
    )
    target = State(
        f"{name}:target",
        {"applicability": AssuranceState.PRESERVED},
        target_context,
        rule,
    )
    return source, target


@pytest.mark.parametrize("domain", DOMAINS, ids=[d[0] for d in DOMAINS])
def test_cross_domain_material_context_shift_fails_closed(domain):
    source, target = _states(domain)
    result = assess_transition(
        EvidentiaryEnvelope(
            transition_id=f"T-{domain[0]}-MISAPPLY",
            source=source,
            target=target,
            material_properties=frozenset({"applicability"}),
            consequence="critical",
        )
    )
    assert result["state"] == "INVALIDATED"
    assert result["decision"] == "DENY"
    assert result["failure"] == "MISAPPLICATION"
    assert result["fail_closed"] is True


@pytest.mark.parametrize("domain", DOMAINS, ids=[d[0] for d in DOMAINS])
def test_cross_domain_unknown_never_promotes_from_target_declaration(domain):
    source, _ = _states(domain)
    unknown_source = State(
        source.state_id,
        {"applicability": AssuranceState.UNKNOWN},
        source.context,
        source.rule,
    )
    target = State(
        f"{domain[0]}:same-context-target",
        {"applicability": AssuranceState.PRESERVED},
        source.context,
        source.rule,
    )
    result = assess_transition(
        EvidentiaryEnvelope(
            transition_id=f"T-{domain[0]}-UNKNOWN",
            source=unknown_source,
            target=target,
            material_properties=frozenset(),
        )
    )
    assert result["state"] == "UNKNOWN"
    assert result["decision"] == "DEFER"


@pytest.mark.parametrize("domain", DOMAINS, ids=[d[0] for d in DOMAINS])
def test_cross_domain_singleton_narrowing_is_not_resolution(domain):
    name = domain[0]
    constraint = Constraint(
        constraint_id=f"{name}:constraint",
        proposition="Candidate Y is excluded.",
        premise_refs=(f"{name}:premise",),
        premise_states={f"{name}:premise": PremiseState.ESTABLISHED},
        provenance_refs=(f"prov:{name}:premise",),
        entailment_basis="Declared premise entails exclusion of Y for this test domain.",
        entailment_status=EntailmentStatus.ESTABLISHED,
        excluded_candidates=("Y",),
        source_ref=f"source:{name}:constraint",
    )
    space = create_answer_space(
        question_id=f"{name}:question",
        candidates=("X", "Y"),
        granularity="binary candidate identity",
        granularity_basis=f"{name} test question is explicitly represented as X/Y.",
    )
    result = recompute_with_constraints(space, (constraint,)).snapshot
    assert result.admissible_candidates == ("X",)
    assert result.resolution_state is ResolutionState.CONSTRAINED
    assert result.epistemic_standing is EpistemicStanding.DERIVED


@pytest.mark.parametrize("domain", DOMAINS, ids=[d[0] for d in DOMAINS])
def test_cross_domain_computational_discovery_is_not_observation(domain):
    name = domain[0]
    source = EpistemicSourceRecord(
        source_id=f"{name}:computation",
        source_type=EpistemicSourceType.COMPUTATIONAL_DISCOVERY,
        producer=f"{name}:analysis-engine",
        provenance_refs=(f"prov:{name}:inputs",),
        input_refs=(f"{name}:input:1",),
        external_origin=False,
    )
    result = observation_reclassification_allowed(source)
    assert result.valid is False
    assert result.reason_code == "NEW_OBSERVATION_REQUIRED"


@pytest.mark.parametrize("domain", DOMAINS, ids=[d[0] for d in DOMAINS])
def test_cross_domain_missing_evidence_availability_remains_unknown(domain):
    name = domain[0]
    result = assess_temporal_availability(
        evidence_id=f"{name}:evidence",
        state_at=AT,
        availability=None,
    )
    assert result.status is TemporalAvailability.UNKNOWN
    assert result.trusted is False
    assert result.reason_code == "AVAILABILITY_UNKNOWN"


@pytest.mark.parametrize("domain", DOMAINS, ids=[d[0] for d in DOMAINS])
def test_cross_domain_circular_justification_is_detected(domain):
    name = domain[0]
    a = f"{name}:claim"
    b = f"{name}:evidence"
    c = f"{name}:constraint"
    graph = JustificationGraph(
        nodes={
            a: JustificationNode(a, JustificationNodeType.CLAIM, (f"prov:{a}",)),
            b: JustificationNode(b, JustificationNodeType.EVIDENCE, (f"prov:{b}",), external_origin=True),
            c: JustificationNode(c, JustificationNodeType.CONSTRAINT, (f"prov:{c}",)),
        },
        edges=(
            SupportEdge(a, b, SupportRelation.SUPPORTS, f"prov:{a}->{b}"),
            SupportEdge(b, c, SupportRelation.CONSTRAINT_INPUT, f"prov:{b}->{c}"),
            SupportEdge(c, a, SupportRelation.SUPPORTS, f"prov:{c}->{a}"),
        ),
    )
    cycle = detect_cycle(graph)
    assert cycle.cyclic is True
    assert {a, b, c}.issubset(set(cycle.cycle_nodes))
