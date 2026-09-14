"""Integration gate for domain-neutral EvidentiaryState and public EPM façade."""
from datetime import datetime, timezone

from dpie_assurance import AssuranceContext, AssuranceState, RuleBinding, State
from epm_constraints import Constraint, ConstraintStatus, EntailmentStatus, PremiseState
from epm_engine import inspect_state
from epm_justification import (
    JustificationGraph,
    JustificationNode,
    JustificationNodeType,
    SupportEdge,
    SupportRelation,
    add_node,
    add_support_edge,
    empty_graph,
)
from epm_resolution import create_answer_space, recompute_with_constraints
from epm_sources import EpistemicSourceRecord, EpistemicSourceType
from epm_state import EvidentiaryState
from epm_temporal import TemporalAvailability

UTC = timezone.utc
AT = datetime(2026, 8, 28, 14, 0, tzinfo=UTC)


def _assurance_state(state_id="E-STATE"):
    return State(
        state_id,
        {"applicability": AssuranceState.PRESERVED},
        AssuranceContext(None, "research", "record", "TX", AT),
        RuleBinding("generic-rule", "1", "generic-authority", "TX", AT),
    )


def _source():
    return EpistemicSourceRecord(
        source_id="OBS-1",
        source_type=EpistemicSourceType.OBSERVATION,
        producer="external-sensor",
        provenance_refs=("prov:OBS-1",),
        external_origin=True,
    )


def _constraint(premise_state=PremiseState.ESTABLISHED):
    return Constraint(
        constraint_id="CST-1",
        proposition="Y is excluded.",
        premise_refs=("P1",),
        premise_states={"P1": premise_state},
        provenance_refs=("prov:P1",),
        entailment_basis="P1 entails exclusion of Y.",
        entailment_status=EntailmentStatus.ESTABLISHED,
        excluded_candidates=("Y",),
        source_ref="source:CST-1",
    )


def _acyclic_graph():
    graph = empty_graph()
    for node in (
        JustificationNode("E", JustificationNodeType.EVIDENCE, ("prov:E",), external_origin=True),
        JustificationNode("CLAIM", JustificationNodeType.CLAIM, ("prov:CLAIM",)),
    ):
        graph = add_node(graph, node).graph
    return add_support_edge(
        graph,
        SupportEdge("E", "CLAIM", SupportRelation.SUPPORTS, "prov:E->CLAIM"),
    ).graph


def test_integrated_state_preserves_component_boundaries_without_collapse():
    constraint = _constraint()
    answer = recompute_with_constraints(
        create_answer_space(
            question_id="Q-1",
            candidates=("X", "Y"),
            granularity="binary identity",
            granularity_basis="Declared test question is X/Y.",
        ),
        (constraint,),
    ).snapshot
    report = inspect_state(
        EvidentiaryState(
            state_id="STATE-1",
            proposition="Which candidate is admissible?",
            assurance_state=_assurance_state(),
            sources=(_source(),),
            constraints=(constraint,),
            answer_space=answer,
            justification_graph=_acyclic_graph(),
        )
    )
    assert report.structural_issues == ()
    assert report.source_results[0].valid is True
    assert report.constraint_results[0].status is ConstraintStatus.VALID
    assert report.answer_space_result.valid is True
    assert report.graph_cycle_result.cyclic is False
    assert not hasattr(report, "confidence")
    assert not hasattr(report, "decision")


def test_invalid_constraint_remains_visible_not_silently_discarded():
    invalid = _constraint(PremiseState.INVALIDATED)
    report = inspect_state(
        EvidentiaryState(
            state_id="STATE-INVALID-C",
            proposition="Constraint state is preserved.",
            assurance_state=_assurance_state(),
            constraints=(invalid,),
        )
    )
    assert len(report.constraint_results) == 1
    assert report.constraint_results[0].status is ConstraintStatus.INVALIDATED


def test_missing_availability_is_reported_unknown_not_invented():
    report = inspect_state(
        EvidentiaryState(
            state_id="STATE-NO-AVAIL",
            proposition="Evidence availability is not supplied.",
            assurance_state=_assurance_state("E-NO-AVAIL"),
        )
    )
    assert len(report.availability_results) == 1
    assert report.availability_results[0].status is TemporalAvailability.UNKNOWN
    assert report.availability_results[0].reason_code == "AVAILABILITY_UNKNOWN"


def test_imported_graph_cycle_remains_visible_when_other_components_are_valid():
    nodes = {
        "A": JustificationNode("A", JustificationNodeType.CLAIM, ("prov:A",)),
        "B": JustificationNode("B", JustificationNodeType.EVIDENCE, ("prov:B",), external_origin=True),
    }
    cyclic = JustificationGraph(
        nodes=nodes,
        edges=(
            SupportEdge("A", "B", SupportRelation.SUPPORTS, "p1"),
            SupportEdge("B", "A", SupportRelation.SUPPORTS, "p2"),
        ),
    )
    report = inspect_state(
        EvidentiaryState(
            state_id="STATE-CYCLE",
            proposition="Circular support must remain visible.",
            assurance_state=_assurance_state(),
            sources=(_source(),),
            justification_graph=cyclic,
        )
    )
    assert report.source_results[0].valid is True
    assert report.graph_cycle_result.cyclic is True


def test_limitations_and_unresolved_conditions_survive_inspection_unchanged():
    limitations = ("sensor calibration not independently replicated",)
    unresolved = ("await second laboratory observation",)
    report = inspect_state(
        EvidentiaryState(
            state_id="STATE-LIMITS",
            proposition="Preserve epistemic boundaries.",
            assurance_state=_assurance_state(),
            limitations=limitations,
            unresolved_conditions=unresolved,
        )
    )
    assert report.limitations == limitations
    assert report.unresolved_conditions == unresolved


def test_state_inspection_does_not_issue_authorization():
    report = inspect_state(
        EvidentiaryState(
            state_id="STATE-NO-AUTH",
            proposition="Inspection is not authorization.",
            assurance_state=_assurance_state(),
            justification_graph=_acyclic_graph(),
        )
    )
    assert not hasattr(report, "decision")
    assert not hasattr(report, "authorized")
