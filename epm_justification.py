"""Justification and dependency graph for EPM vNext.

The graph records support and dependency structure. It does not authorize
actions and it does not upgrade epistemic state merely because a graph is
acyclic.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from enum import Enum


class JustificationNodeType(str, Enum):
    CLAIM = "CLAIM"
    EVIDENCE = "EVIDENCE"
    CONSTRAINT = "CONSTRAINT"
    DERIVATION = "DERIVATION"
    DISCRIMINATOR = "DISCRIMINATOR"
    ATTESTATION = "ATTESTATION"
    DECISION = "DECISION"


class JustificationNodeStatus(str, Enum):
    ACTIVE = "ACTIVE"
    STALE = "STALE"
    INVALIDATED = "INVALIDATED"
    CONTRADICTED = "CONTRADICTED"


class SupportRelation(str, Enum):
    SUPPORTS = "SUPPORTS"
    DERIVATION_INPUT = "DERIVATION_INPUT"
    CONSTRAINT_INPUT = "CONSTRAINT_INPUT"
    DISCRIMINATOR_INPUT = "DISCRIMINATOR_INPUT"
    ATTESTS = "ATTESTS"
    DECISION_BASIS = "DECISION_BASIS"


class SupportStatus(str, Enum):
    ESTABLISHED = "ESTABLISHED"
    UNSUPPORTED = "UNSUPPORTED"
    STALE = "STALE"
    INVALID = "INVALID"
    CIRCULAR = "CIRCULAR"


@dataclass(frozen=True)
class JustificationNode:
    node_id: str
    node_type: JustificationNodeType
    provenance_refs: tuple[str, ...]
    external_origin: bool = False
    status: JustificationNodeStatus = JustificationNodeStatus.ACTIVE


@dataclass(frozen=True)
class SupportEdge:
    source_id: str
    target_id: str
    relation: SupportRelation
    provenance_ref: str


@dataclass(frozen=True)
class InvalidationEvent:
    origin_id: str
    affected_ids: tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class JustificationGraph:
    nodes: Mapping[str, JustificationNode]
    edges: tuple[SupportEdge, ...] = ()
    invalidation_history: tuple[InvalidationEvent, ...] = ()


@dataclass(frozen=True)
class GraphOperationResult:
    graph: JustificationGraph
    accepted: bool
    reason_code: str
    reason: str


@dataclass(frozen=True)
class CycleResult:
    cyclic: bool
    cycle_nodes: tuple[str, ...] = ()


@dataclass(frozen=True)
class IndependenceResult:
    independent: bool
    reason_code: str
    reason: str
    roots_a: tuple[str, ...] = ()
    roots_b: tuple[str, ...] = ()


@dataclass(frozen=True)
class SupportAssessment:
    target_id: str
    status: SupportStatus
    reason_code: str
    reason: str


def empty_graph() -> JustificationGraph:
    return JustificationGraph(nodes={})


def add_node(graph: JustificationGraph, node: JustificationNode) -> GraphOperationResult:
    if not node.node_id.strip():
        return GraphOperationResult(
            graph,
            False,
            "NODE_ID_REQUIRED",
            "Node identity is required.",
        )
    if not node.provenance_refs or any(not ref.strip() for ref in node.provenance_refs):
        return GraphOperationResult(
            graph,
            False,
            "NODE_PROVENANCE_REQUIRED",
            "Justification nodes require non-empty provenance references.",
        )
    if node.node_id in graph.nodes:
        return GraphOperationResult(
            graph,
            False,
            "NODE_ALREADY_EXISTS",
            "Node identity is immutable and already exists in the graph.",
        )
    nodes = dict(graph.nodes)
    nodes[node.node_id] = node
    return GraphOperationResult(
        replace(graph, nodes=nodes),
        True,
        "NODE_ADDED",
        "Node added without changing existing graph state.",
    )


def _adjacency(graph: JustificationGraph) -> dict[str, tuple[str, ...]]:
    adjacency: dict[str, list[str]] = {node_id: [] for node_id in graph.nodes}
    for edge in graph.edges:
        adjacency.setdefault(edge.source_id, []).append(edge.target_id)
    return {key: tuple(values) for key, values in adjacency.items()}


def _reverse_adjacency(graph: JustificationGraph) -> dict[str, tuple[str, ...]]:
    reverse: dict[str, list[str]] = {node_id: [] for node_id in graph.nodes}
    for edge in graph.edges:
        reverse.setdefault(edge.target_id, []).append(edge.source_id)
    return {key: tuple(values) for key, values in reverse.items()}


def _path_exists(graph: JustificationGraph, start: str, target: str) -> bool:
    adjacency = _adjacency(graph)
    stack = [start]
    visited = set()
    while stack:
        current = stack.pop()
        if current == target:
            return True
        if current in visited:
            continue
        visited.add(current)
        stack.extend(adjacency.get(current, ()))
    return False


def detect_cycle(graph: JustificationGraph) -> CycleResult:
    adjacency = _adjacency(graph)
    state: dict[str, int] = {node_id: 0 for node_id in graph.nodes}
    stack: list[str] = []

    def visit(node_id: str) -> tuple[str, ...] | None:
        state[node_id] = 1
        stack.append(node_id)
        for nxt in adjacency.get(node_id, ()):
            if nxt not in state:
                state[nxt] = 0
            if state[nxt] == 0:
                found = visit(nxt)
                if found:
                    return found
            elif state[nxt] == 1:
                start = stack.index(nxt)
                return tuple(stack[start:] + [nxt])
        stack.pop()
        state[node_id] = 2
        return None

    for node_id in tuple(state):
        if state[node_id] == 0:
            found = visit(node_id)
            if found:
                return CycleResult(True, found)
    return CycleResult(False, ())


def add_support_edge(
    graph: JustificationGraph,
    edge: SupportEdge,
) -> GraphOperationResult:
    if edge.source_id not in graph.nodes or edge.target_id not in graph.nodes:
        return GraphOperationResult(
            graph,
            False,
            "EDGE_NODE_MISSING",
            "Both edge endpoints must already exist in the graph.",
        )
    if not edge.provenance_ref.strip():
        return GraphOperationResult(
            graph,
            False,
            "EDGE_PROVENANCE_REQUIRED",
            "Support relation provenance is required.",
        )
    if edge.source_id == edge.target_id:
        return GraphOperationResult(
            graph,
            False,
            "CIRCULAR_SUPPORT",
            "A node cannot directly support itself.",
        )
    if _path_exists(graph, edge.target_id, edge.source_id):
        return GraphOperationResult(
            graph,
            False,
            "CIRCULAR_SUPPORT",
            "The proposed support edge would create a circular justification path.",
        )
    if edge in graph.edges:
        return GraphOperationResult(
            graph,
            False,
            "EDGE_ALREADY_EXISTS",
            "The exact support relation is already recorded.",
        )
    updated = replace(graph, edges=graph.edges + (edge,))
    return GraphOperationResult(
        updated,
        True,
        "EDGE_ADDED",
        "Support relation added without creating circular justification.",
    )


def _ancestors(graph: JustificationGraph, node_id: str) -> tuple[str, ...]:
    reverse = _reverse_adjacency(graph)
    visited = set()
    stack = list(reverse.get(node_id, ()))
    while stack:
        current = stack.pop()
        if current in visited:
            continue
        visited.add(current)
        stack.extend(reverse.get(current, ()))
    return tuple(sorted(visited))


def _external_roots(graph: JustificationGraph, node_id: str) -> tuple[str, ...]:
    reverse = _reverse_adjacency(graph)
    ancestors = set(_ancestors(graph, node_id)) | {node_id}
    roots = []
    for candidate in sorted(ancestors):
        node = graph.nodes.get(candidate)
        if node is None or not node.external_origin:
            continue
        upstream_in_scope = [
            source
            for source in reverse.get(candidate, ())
            if source in ancestors
        ]
        if not upstream_in_scope:
            roots.append(candidate)
    return tuple(roots)


def _directly_supports(
    graph: JustificationGraph,
    source_id: str,
    target_id: str,
) -> bool:
    return any(
        edge.source_id == source_id and edge.target_id == target_id
        for edge in graph.edges
    )


def assess_independence(
    graph: JustificationGraph,
    *,
    support_a: str,
    support_b: str,
    target_id: str,
) -> IndependenceResult:
    cycle = detect_cycle(graph)
    if cycle.cyclic:
        return IndependenceResult(
            False,
            "CIRCULAR_GRAPH",
            "Circular justification cannot count as independent corroboration.",
        )
    if support_a == support_b:
        return IndependenceResult(
            False,
            "SAME_SUPPORT",
            "A support node is not independent corroboration of itself.",
        )
    if not _directly_supports(
        graph, support_a, target_id
    ) or not _directly_supports(graph, support_b, target_id):
        return IndependenceResult(
            False,
            "TARGET_SUPPORT_REQUIRED",
            "Both candidate support paths must contribute to the same target.",
        )
    roots_a = _external_roots(graph, support_a)
    roots_b = _external_roots(graph, support_b)
    if not roots_a or not roots_b:
        return IndependenceResult(
            False,
            "EXTERNAL_ROOT_REQUIRED",
            "Independent corroboration requires non-empty external-origin root sets.",
            roots_a,
            roots_b,
        )
    overlap = set(roots_a).intersection(roots_b)
    if overlap:
        return IndependenceResult(
            False,
            "SHARED_ORIGIN",
            "Support paths share upstream external-origin evidence and are correlated rather than independent.",
            roots_a,
            roots_b,
        )
    return IndependenceResult(
        True,
        "INDEPENDENT_SUPPORT",
        "Support paths have disjoint external-origin roots and no circular dependency.",
        roots_a,
        roots_b,
    )


def invalidate_node(
    graph: JustificationGraph,
    *,
    node_id: str,
    reason: str,
    contradicted: bool = False,
) -> GraphOperationResult:
    if node_id not in graph.nodes:
        return GraphOperationResult(
            graph,
            False,
            "NODE_MISSING",
            "Cannot invalidate a node that is not present.",
        )
    adjacency = _adjacency(graph)
    affected = set()
    stack = list(adjacency.get(node_id, ()))
    while stack:
        current = stack.pop()
        if current in affected:
            continue
        affected.add(current)
        stack.extend(adjacency.get(current, ()))
    nodes = dict(graph.nodes)
    origin_status = (
        JustificationNodeStatus.CONTRADICTED
        if contradicted
        else JustificationNodeStatus.INVALIDATED
    )
    nodes[node_id] = replace(nodes[node_id], status=origin_status)
    for affected_id in affected:
        current = nodes[affected_id]
        if current.status is JustificationNodeStatus.ACTIVE:
            nodes[affected_id] = replace(current, status=JustificationNodeStatus.STALE)
    event = InvalidationEvent(node_id, tuple(sorted(affected)), reason)
    updated = replace(
        graph,
        nodes=nodes,
        invalidation_history=graph.invalidation_history + (event,),
    )
    return GraphOperationResult(
        updated,
        True,
        "INVALIDATION_PROPAGATED",
        "Upstream invalidation was propagated to every reachable dependent node.",
    )


def assess_target_support(
    graph: JustificationGraph,
    target_id: str,
) -> SupportAssessment:
    target = graph.nodes.get(target_id)
    if target is None:
        return SupportAssessment(
            target_id,
            SupportStatus.UNSUPPORTED,
            "TARGET_MISSING",
            "Target node is not present in the justification graph.",
        )
    cycle = detect_cycle(graph)
    if cycle.cyclic and target_id in cycle.cycle_nodes:
        return SupportAssessment(
            target_id,
            SupportStatus.CIRCULAR,
            "CIRCULAR_SUPPORT",
            "Target participates in circular justification.",
        )
    incoming = [edge for edge in graph.edges if edge.target_id == target_id]
    if not incoming:
        return SupportAssessment(
            target_id,
            SupportStatus.UNSUPPORTED,
            "NO_SUPPORT",
            "Target has no recorded incoming justification relation.",
        )
    if any(not edge.provenance_ref.strip() for edge in incoming):
        return SupportAssessment(
            target_id,
            SupportStatus.INVALID,
            "EDGE_PROVENANCE_REQUIRED",
            "At least one incoming support relation lacks provenance.",
        )
    relevant = set(_ancestors(graph, target_id)) | {target_id}
    statuses = {
        graph.nodes[node_id].status
        for node_id in relevant
        if node_id in graph.nodes
    }
    if (
        JustificationNodeStatus.CONTRADICTED in statuses
        or JustificationNodeStatus.INVALIDATED in statuses
    ):
        return SupportAssessment(
            target_id,
            SupportStatus.INVALID,
            "UPSTREAM_INVALID",
            "Target depends on invalidated or contradicted support.",
        )
    if JustificationNodeStatus.STALE in statuses:
        return SupportAssessment(
            target_id,
            SupportStatus.STALE,
            "UPSTREAM_STALE",
            "Target or an upstream dependency is stale and requires re-evaluation.",
        )
    if cycle.cyclic:
        return SupportAssessment(
            target_id,
            SupportStatus.CIRCULAR,
            "CIRCULAR_GRAPH",
            "Graph contains circular justification and cannot establish current support.",
        )
    return SupportAssessment(
        target_id,
        SupportStatus.ESTABLISHED,
        "SUPPORT_ESTABLISHED",
        "Recorded support is acyclic, provenance-bearing, and currently active. This does not grant authorization.",
    )
