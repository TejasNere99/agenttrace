from __future__ import annotations

from typing import Any

import networkx as nx

from app.graph.graph_builder import GraphBuildResult


class PropagationAnalyzer:
    """Describe graph descendants of recorded failures without assuming impact."""

    def analyze(self, result: GraphBuildResult, failure_records: list[dict[str, Any]]) -> dict[str, Any]:
        graph = result.graph
        by_event: dict[str, dict[str, Any]] = {}
        per_failure: list[dict[str, Any]] = []
        recovery_records: list[dict[str, Any]] = []
        for failure in failure_records:
            failure_id = failure.get("event_id")
            if failure_id not in graph:
                per_failure.append({"failure_event_id": failure_id, "downstream_events": [], "recovered": False})
                continue
            distances = _descendant_distances(graph, failure_id)
            ordered = sorted(distances, key=lambda node: _node_sort(graph, node))
            downstream = []
            for event_id in ordered:
                attrs = graph.nodes[event_id]
                distance = distances[event_id]
                classification = _status_class(attrs.get("status"))
                item = {
                    "event_id": event_id,
                    "sequence_number": attrs.get("sequence_number"),
                    "event_type": attrs.get("event_type"),
                    "event_name": attrs.get("name"),
                    "status": attrs.get("status"),
                    "dependency_distance": distance,
                    "impact_classification": classification,
                }
                downstream.append(item)
                combined = by_event.setdefault(event_id, {
                    **item,
                    "failure_event_ids": [],
                    "distance_by_failure": {},
                })
                combined["failure_event_ids"].append(failure_id)
                combined["distance_by_failure"][failure_id] = distance

            recovery = _recovery_evidence(graph, failure_id, distances)
            recovery_records.append({"failure_event_id": failure_id, **recovery})
            per_failure.append({"failure_event_id": failure_id, "downstream_events": downstream, **recovery})

        downstream_events = sorted(by_event.values(), key=lambda item: _node_sort(graph, item["event_id"]))
        for item in downstream_events:
            item["failure_event_ids"].sort(key=lambda event_id: _node_sort(graph, event_id) if event_id in graph else (2**63, event_id))
        direct_ids = {event_id for event_id, item in by_event.items() if min(item["distance_by_failure"].values()) == 1}
        indirect_ids = set(by_event) - direct_ids
        counts = {
            "potentially_affected_count": len(by_event),
            "directly_dependent_count": len(direct_ids),
            "indirectly_dependent_count": len(indirect_ids),
            "failed_downstream_count": sum(item["impact_classification"] == "failed" for item in downstream_events),
            "completed_successfully_downstream_count": sum(item["impact_classification"] == "completed_successfully" for item in downstream_events),
            "skipped_downstream_count": sum(item["impact_classification"] == "skipped" for item in downstream_events),
            "status_unknown_downstream_count": sum(item["impact_classification"] == "status_unknown" for item in downstream_events),
        }
        recorded_recovery = any(item["recovery_recorded"] for item in recovery_records)
        successful_recovery = any(item["recovered"] for item in recovery_records)
        return {
            **counts,
            "recovered": successful_recovery,
            "recovery_recorded": recorded_recovery,
            "recovery_by_failure": recovery_records,
            "failures": per_failure,
            "downstream_events": downstream_events,
        }


def _descendant_distances(graph: nx.DiGraph, source: str) -> dict[str, int]:
    distances = {node: 1 for node in graph.successors(source)}
    queue = list(graph.successors(source))
    index = 0
    while index < len(queue):
        node = queue[index]
        index += 1
        next_distance = distances[node] + 1
        for child in graph.successors(node):
            if child == source:
                continue
            if child not in distances or next_distance < distances[child]:
                distances[child] = next_distance
                queue.append(child)
    return distances


def _status_class(status: Any) -> str:
    if status == "failed":
        return "failed"
    if status == "success":
        return "completed_successfully"
    if status == "skipped":
        return "skipped"
    return "potentially_affected" if status in {"pending", "running"} else "status_unknown"


def _recovery_evidence(graph: nx.DiGraph, failure_id: str, distances: dict[str, int]) -> dict[str, Any]:
    recoveries = [
        node for node in distances
        if graph.nodes[node].get("event_type") == "recovery" and graph.nodes[node].get("status") == "success"
    ]
    recoveries.sort(key=lambda node: _node_sort(graph, node))
    successful_completions: list[str] = []
    for recovery_id in recoveries:
        descendants = nx.descendants(graph, recovery_id)
        successful_completions.extend(
            node for node in descendants
            if graph.nodes[node].get("event_type") == "task_complete" and graph.nodes[node].get("status") == "success"
        )
    successful_completions = sorted(set(successful_completions), key=lambda node: _node_sort(graph, node))
    return {
        "recovery_recorded": bool(recoveries),
        "recovery_event_ids": recoveries,
        "successful_completion_after_recovery": bool(successful_completions),
        "completion_event_ids": successful_completions,
        "recovered": bool(recoveries and successful_completions),
    }


def _node_sort(graph: nx.DiGraph, node: str) -> tuple[int, str]:
    sequence = graph.nodes[node].get("sequence_number")
    return (sequence if isinstance(sequence, int) and not isinstance(sequence, bool) else 2**63, node)
