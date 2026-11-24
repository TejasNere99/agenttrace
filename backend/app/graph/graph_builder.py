from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

import networkx as nx


_EVENT_TYPES = {
    "task_start", "planning", "llm_call", "tool_call", "tool_result",
    "code_execution", "validation", "error", "recovery", "task_complete",
}


@dataclass(frozen=True)
class GraphBuildResult:
    run_id: str
    graph: nx.DiGraph
    validation_issues: list[dict[str, Any]]
    topological_order: list[str]
    statistics: dict[str, Any]

    @property
    def graph_valid(self) -> bool:
        return not self.validation_issues


class GraphBuilder:
    """Build a directed dependency graph from persisted trace events."""

    def build(
        self,
        run_id: str,
        events: Iterable[dict[str, Any]],
        *,
        external_parent_run_ids: dict[str, str] | None = None,
    ) -> GraphBuildResult:
        graph = nx.DiGraph(run_id=run_id)
        issues: list[dict[str, Any]] = []
        external_parent_run_ids = external_parent_run_ids or {}
        seen: dict[str, dict[str, Any]] = {}
        event_list = list(events)

        for event in event_list:
            event_id = _event_id(event)
            if event_id is None:
                issues.append(_issue("missing_event_id", "Trace event has no usable event ID."))
                continue
            if event_id in seen:
                issues.append(_issue("duplicate_event_id", "Trace contains duplicate event IDs.", event_id=event_id))
                continue
            seen[event_id] = event
            if str(event.get("run_id", run_id)) != run_id:
                issues.append(_issue("cross_run_event", "Trace event belongs to a different run.", event_id=event_id))
            event_type = _enum_value(event.get("event_type"))
            status = _enum_value(event.get("status"))
            if event_type not in _EVENT_TYPES:
                issues.append(_issue("invalid_event_type", "Trace event has no valid event type.", event_id=event_id))
            if status not in {"pending", "running", "success", "failed", "skipped"}:
                issues.append(_issue("invalid_event_status", "Trace event has an unsupported status.", event_id=event_id))
            sequence = event.get("sequence_number")
            if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 1:
                issues.append(_issue("invalid_sequence_number", "Trace event has an invalid sequence number.", event_id=event_id))
            graph.add_node(
                event_id,
                event_id=event_id,
                run_id=str(event.get("run_id", run_id)),
                sequence_number=sequence,
                name=str(event.get("name") or event_type or "Trace event"),
                event_type=event_type,
                status=status if isinstance(status, str) else None,
                timestamp=event.get("timestamp"),
                duration_ms=event.get("duration_ms"),
                error=bool(event.get("error")) or status == "failed" or event_type == "error",
                metadata=_safe_metadata(event.get("metadata")),
            )

        for event_id, event in seen.items():
            parent_id = _reference_id(event.get("parent_event_id"))
            if parent_id is None:
                continue
            if parent_id == event_id:
                issues.append(_issue("self_reference", "Event cannot depend on itself.", event_id=event_id, parent_event_id=parent_id))
                continue
            if parent_id not in seen:
                external_run = external_parent_run_ids.get(parent_id)
                code = "cross_run_reference" if external_run is not None else "missing_parent_reference"
                message = "Parent event belongs to another run." if external_run is not None else "Parent event is not present in this run's trace."
                details: dict[str, Any] = {"event_id": event_id, "parent_event_id": parent_id}
                if external_run is not None:
                    details["parent_run_id"] = external_run
                issues.append(_issue(code, message, **details))
                continue
            parent = seen[parent_id]
            parent_run = str(parent.get("run_id", run_id))
            child_run = str(event.get("run_id", run_id))
            if parent_run != child_run or child_run != run_id:
                issues.append(_issue("cross_run_reference", "Dependency endpoints must belong to the requested run.", event_id=event_id, parent_event_id=parent_id))
                continue
            if not graph.has_node(parent_id) or not graph.has_node(event_id):
                issues.append(_issue("invalid_relationship", "Dependency endpoints could not be represented as graph nodes.", event_id=event_id, parent_event_id=parent_id))
                continue
            graph.add_edge(parent_id, event_id, source=parent_id, target=event_id, relationship_type="dependency")

        topological_order: list[str] = []
        if not nx.is_directed_acyclic_graph(graph):
            try:
                cycle = nx.find_cycle(graph, orientation="original")
                cycle_ids = [edge[0] for edge in cycle] + ([cycle[-1][1]] if cycle else [])
            except nx.NetworkXNoCycle:
                cycle_ids = []
            issues.append(_issue("circular_dependency", "Execution dependency graph contains a cycle.", event_ids=cycle_ids))
        else:
            topological_order = list(
                nx.lexicographical_topological_sort(
                    graph,
                    key=lambda node: (graph.nodes[node].get("sequence_number") or 0, node),
                )
            )

        roots = sorted((node for node, degree in graph.in_degree() if degree == 0), key=lambda node: _node_sort(graph, node))
        leaves = sorted((node for node, degree in graph.out_degree() if degree == 0), key=lambda node: _node_sort(graph, node))
        branching = sorted((node for node, degree in graph.out_degree() if degree > 1), key=lambda node: _node_sort(graph, node))
        components = list(nx.weakly_connected_components(graph)) if graph.number_of_nodes() else []
        max_depth: int | None = None
        if topological_order:
            depths: dict[str, int] = {}
            for node in topological_order:
                parent_depth = max((depths[parent] + 1 for parent in graph.predecessors(node)), default=0)
                depths[node] = parent_depth
            max_depth = max(depths.values(), default=0)
        elif graph.number_of_nodes() == 0:
            max_depth = 0

        statistics = {
            "node_count": graph.number_of_nodes(),
            "edge_count": graph.number_of_edges(),
            "root_count": len(roots),
            "leaf_count": len(leaves),
            "roots": roots,
            "leaves": leaves,
            "branching_points": branching,
            "topological_order": topological_order,
            "max_depth": max_depth,
            "disconnected_component_count": len(components),
        }
        return GraphBuildResult(run_id, graph, issues, topological_order, statistics)


def _event_id(event: dict[str, Any]) -> str | None:
    value = event.get("event_id", event.get("id", event.get("_id")))
    return _reference_id(value)


def _reference_id(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "hex"):
        return str(value)
    value = str(value).strip()
    return value or None


def _enum_value(value: Any) -> Any:
    return value.value if hasattr(value, "value") else value


def _safe_metadata(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    # Metadata is useful for labels/classification. Payloads remain available via /events.
    return {key: item for key, item in value.items() if isinstance(item, (str, int, float, bool)) or item is None}


def _node_sort(graph: nx.DiGraph, node: str) -> tuple[int, str]:
    sequence = graph.nodes[node].get("sequence_number")
    return (sequence if isinstance(sequence, int) and not isinstance(sequence, bool) else 2**63, node)


def _issue(code: str, message: str, **details: Any) -> dict[str, Any]:
    return {"code": code, "message": message, **details}
