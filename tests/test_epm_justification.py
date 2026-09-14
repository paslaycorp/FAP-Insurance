"""Adversarial gate for EPM justification/dependency graph v0.1."""
from epm_justification import (
    JustificationGraph,
    JustificationNode,
    JustificationNodeStatus,
    JustificationNodeType,
    SupportEdge,
    SupportRelation,
    SupportStatus,
    add_node,
    add_support_edge,
    assess_independence,
    assess_target_support,
    detect_cycle,
    empty_graph,
    invalidate_node,
)


def _node(node_id, node_type, *, external=False):
    return JustificationNode(
        node_id=node_id,
        node_type=node_type,
        provenance_refs=(f"prov:{node_id}",),
        external_origin=external,
    )


def _add(graph, *nodes):
    for node in nodes:
        result = add_node(graph, node)
        assert result.accepted is True
        graph = result.graph
    return graph


def _edge(graph, source, target, relation=SupportRelation.SUPPORTS):
    result = add_support_edge(
        graph,
        SupportEdge(source, target, relation, f"prov:{source}->{target}"),
    )
    assert result.accepted is True
    return result.graph


def test_direct_self_support_is_rejected():
    graph = _add(empty_graph(), _node("A", JustificationNodeType.CLAIM))
    result = add_support_edge(
        graph,
        SupportEdge("A", "A", SupportRelation.SUPPORTS, "prov:self"),
    )
    assert result.accepted is False
    assert result.reason_code == "CIRCULAR_SUPPORT"


def test_multinode_circular_support_is_rejected():
    graph = _add(
        empty_graph(),
        _node("A", JustificationNodeType.CLAIM),
        _node("B", JustificationNodeType.EVIDENCE, external=True),
        _node("C", JustificationNodeType.CONSTRAINT),
    )
    graph = _edge(graph, "A", "B")
    graph = _edge(graph, "B", "C", SupportRelation.CONSTRAINT_INPUT)
    result = add_support_edge(
        graph,
        SupportEdge("C", "A", SupportRelation.SUPPORTS, "prov:C->A"),
    )
    assert result.accepted is False
    assert result.reason_code == "CIRCULAR_SUPPORT"


def test_imported_cyclic_graph_is_detected():
    nodes = {
        "A": _node("A", JustificationNodeType.CLAIM),
        "B": _node("B", JustificationNodeType.EVIDENCE, external=True),
        "C": _node("C", JustificationNodeType.CONSTRAINT),
    }
    graph = JustificationGraph(
        nodes=nodes,
        edges=(
            SupportEdge("A", "B", SupportRelation.SUPPORTS, "p1"),
            SupportEdge("B", "C", SupportRelation.CONSTRAINT_INPUT, "p2"),
            SupportEdge("C", "A", SupportRelation.SUPPORTS, "p3"),
        ),
    )
    cycle = detect_cycle(graph)
    assert cycle.cyclic is True
    assert {"A", "B", "C"}.issubset(set(cycle.cycle_nodes))


def test_shared_external_origin_is_correlated_not_independent():
    graph = _add(
        empty_graph(),
        _node("E0", JustificationNodeType.EVIDENCE, external=True),
        _node("D1", JustificationNodeType.DERIVATION),
        _node("C1", JustificationNodeType.CONSTRAINT),
        _node("TARGET", JustificationNodeType.CLAIM),
    )
    graph = _edge(graph, "E0", "D1", SupportRelation.DERIVATION_INPUT)
    graph = _edge(graph, "E0", "C1", SupportRelation.CONSTRAINT_INPUT)
    graph = _edge(graph, "D1", "TARGET")
    graph = _edge(graph, "C1", "TARGET")
    result = assess_independence(graph, support_a="D1", support_b="C1", target_id="TARGET")
    assert result.independent is False
    assert result.reason_code == "SHARED_ORIGIN"
    assert result.roots_a == ("E0",)
    assert result.roots_b == ("E0",)


def test_disjoint_external_origins_can_be_independent():
    graph = _add(
        empty_graph(),
        _node("E1", JustificationNodeType.EVIDENCE, external=True),
        _node("E2", JustificationNodeType.ATTESTATION, external=True),
        _node("D1", JustificationNodeType.DERIVATION),
        _node("D2", JustificationNodeType.DERIVATION),
        _node("TARGET", JustificationNodeType.CLAIM),
    )
    graph = _edge(graph, "E1", "D1", SupportRelation.DERIVATION_INPUT)
    graph = _edge(graph, "E2", "D2", SupportRelation.DERIVATION_INPUT)
    graph = _edge(graph, "D1", "TARGET")
    graph = _edge(graph, "D2", "TARGET")
    result = assess_independence(graph, support_a="D1", support_b="D2", target_id="TARGET")
    assert result.independent is True
    assert result.reason_code == "INDEPENDENT_SUPPORT"
    assert result.roots_a == ("E1",)
    assert result.roots_b == ("E2",)


def test_upstream_invalidation_marks_all_downstream_dependents_stale():
    graph = _add(
        empty_graph(),
        _node("E", JustificationNodeType.EVIDENCE, external=True),
        _node("C", JustificationNodeType.CONSTRAINT),
        _node("CLAIM", JustificationNodeType.CLAIM),
        _node("DECISION", JustificationNodeType.DECISION),
    )
    graph = _edge(graph, "E", "C", SupportRelation.CONSTRAINT_INPUT)
    graph = _edge(graph, "C", "CLAIM")
    graph = _edge(graph, "CLAIM", "DECISION", SupportRelation.DECISION_BASIS)
    result = invalidate_node(graph, node_id="E", reason="provenance chain invalidated")
    assert result.accepted is True
    updated = result.graph
    assert updated.nodes["E"].status is JustificationNodeStatus.INVALIDATED
    assert updated.nodes["C"].status is JustificationNodeStatus.STALE
    assert updated.nodes["CLAIM"].status is JustificationNodeStatus.STALE
    assert updated.nodes["DECISION"].status is JustificationNodeStatus.STALE
    assert updated.invalidation_history[-1].affected_ids == ("C", "CLAIM", "DECISION")


def test_stale_or_invalidated_path_cannot_establish_current_support():
    graph = _add(
        empty_graph(),
        _node("E", JustificationNodeType.EVIDENCE, external=True),
        _node("CLAIM", JustificationNodeType.CLAIM),
    )
    graph = _edge(graph, "E", "CLAIM")
    assert assess_target_support(graph, "CLAIM").status is SupportStatus.ESTABLISHED
    invalidated = invalidate_node(graph, node_id="E", reason="evidence withdrawn").graph
    assessment = assess_target_support(invalidated, "CLAIM")
    assert assessment.status is SupportStatus.INVALID
    assert assessment.reason_code == "UPSTREAM_INVALID"


def test_clean_decision_basis_does_not_return_authorization():
    graph = _add(
        empty_graph(),
        _node("E", JustificationNodeType.EVIDENCE, external=True),
        _node("DECISION", JustificationNodeType.DECISION),
    )
    graph = _edge(graph, "E", "DECISION", SupportRelation.DECISION_BASIS)
    assessment = assess_target_support(graph, "DECISION")
    assert assessment.status is SupportStatus.ESTABLISHED
    assert assessment.reason_code == "SUPPORT_ESTABLISHED"
    assert "authorization" in assessment.reason.lower()
