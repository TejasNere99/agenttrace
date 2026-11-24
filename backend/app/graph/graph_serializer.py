from __future__ import annotations

from datetime import datetime
from typing import Any

from app.graph.graph_builder import GraphBuildResult


class GraphSerializer:
    """Serialize a graph to stable node and edge data for React Flow layout."""

    def serialize(self, result: GraphBuildResult) -> dict[str, Any]:
        graph = result.graph
        nodes = []
        for event_id, attrs in sorted(
            graph.nodes(data=True),
            key=lambda item: (
                item[1].get("sequence_number") if isinstance(item[1].get("sequence_number"), int) else 2**63,
                item[0],
            ),
        ):
            nodes.append({
                "id": event_id,
                "type": "traceEvent",
                "data": {
                    "event_id": event_id,
                    "run_id": attrs.get("run_id"),
                    "label": attrs.get("name"),
                    "name": attrs.get("name"),
                    "event_type": attrs.get("event_type"),
                    "status": attrs.get("status"),
                    "sequence_number": attrs.get("sequence_number"),
                    "timestamp": _iso(attrs.get("timestamp")),
                    "duration_ms": attrs.get("duration_ms"),
                    "error": attrs.get("error", False),
                    "metadata": attrs.get("metadata", {}),
                },
            })
        edges = [
            {
                "id": f"{source}->{target}",
                "source": source,
                "target": target,
                "type": "dependency",
                "data": {"relationship_type": attrs.get("relationship_type", "dependency")},
            }
            for source, target, attrs in sorted(
                graph.edges(data=True),
                key=lambda edge: (_node_sort_key(graph, edge[0]), _node_sort_key(graph, edge[1])),
            )
        ]
        return {
            "run_id": result.run_id,
            "graph_valid": result.graph_valid,
            "nodes": nodes,
            "edges": edges,
            "statistics": result.statistics,
            "validation_issues": result.validation_issues,
        }


def _node_sort_key(graph: Any, node: str) -> tuple[int, str]:
    value = graph.nodes[node].get("sequence_number")
    return (value if isinstance(value, int) else 2**63, node)


def _iso(value: Any) -> str | None:
    return value.isoformat() if isinstance(value, datetime) else (str(value) if value is not None else None)
