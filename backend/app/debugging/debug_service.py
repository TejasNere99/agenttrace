from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from bson import ObjectId

from app.debugging.failure_detector import FailureDetector
from app.debugging.propagation_analyzer import PropagationAnalyzer
from app.graph.graph_builder import GraphBuilder
from app.graph.graph_serializer import GraphSerializer
from app.services import run_service


class DebugAnalysisService:
    """Read persisted run traces and derive graph and evidence-based debug data."""

    def __init__(self, database: Any) -> None:
        self.database = database
        self.graph_builder = GraphBuilder()
        self.graph_serializer = GraphSerializer()
        self.failure_detector = FailureDetector()
        self.propagation_analyzer = PropagationAnalyzer()

    async def get_graph(self, run_id: str) -> dict[str, Any]:
        run, events, external_parents = await self._load(run_id)
        result = self.graph_builder.build(run_id, events, external_parent_run_ids=external_parents)
        return self.graph_serializer.serialize(result)

    async def get_debug_analysis(self, run_id: str) -> dict[str, Any]:
        run, events, external_parents = await self._load(run_id)
        graph_result = self.graph_builder.build(run_id, events, external_parent_run_ids=external_parents)
        failure_analysis = self.failure_detector.detect(events, run_status=run.get("status"))
        propagation = self.propagation_analyzer.analyze(graph_result, failure_analysis["failure_records"])
        limitations: list[str] = []
        if not graph_result.graph_valid:
            limitations.append("Dependency analysis uses only valid recorded edges; graph validation issues limit downstream conclusions.")
        if failure_analysis["run_status_only_failure"] is not None:
            limitations.append("The run is marked failed, but no failed trace event identifies an event-level failure.")
        if failure_analysis["failure_records"] and not propagation["recovery_recorded"]:
            limitations.append("No successful recovery event is recorded downstream of the detected failure; this does not prove recovery was impossible.")
        if len(events) == 0:
            limitations.append("No trace events were recorded, so event-level failure and dependency analysis is unavailable.")
        if _timestamps_conflict_with_sequence(events):
            limitations.append("One or more event timestamps conflict with sequence order; first detected failure follows sequence number, with timestamp used only as context.")
        return {
            "run_id": run_id,
            "run_status": run.get("status"),
            "synthetic": bool(run.get("synthetic", False)),
            "graph_summary": {
                "node_count": graph_result.statistics["node_count"],
                "edge_count": graph_result.statistics["edge_count"],
                "graph_valid": graph_result.graph_valid,
                "statistics": graph_result.statistics,
                "validation_issues": graph_result.validation_issues,
            },
            "failure_analysis": failure_analysis,
            "propagation_analysis": propagation,
            "downstream_events": propagation["downstream_events"],
            "limitations": limitations,
        }

    async def _load(self, run_id: str) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, str]]:
        run = await run_service.get_run(self.database, run_id)
        cursor = self.database.trace_events.find({"run_id": run_id}).sort([("sequence_number", 1), ("_id", 1)])
        events = await cursor.to_list(length=None)
        event_ids = {str(event.get("_id", event.get("event_id", event.get("id")))) for event in events}
        missing_parent_ids = {
            str(event["parent_event_id"])
            for event in events
            if event.get("parent_event_id") is not None and str(event["parent_event_id"]) not in event_ids
        }
        object_ids = [ObjectId(value) for value in missing_parent_ids if ObjectId.is_valid(value)]
        external_parents: dict[str, str] = {}
        if object_ids:
            parent_cursor = self.database.trace_events.find({"_id": {"$in": object_ids}})
            for parent in await parent_cursor.to_list(length=len(object_ids)):
                parent_id = parent.get("_id", parent.get("event_id", parent.get("id")))
                external_parents[str(parent_id)] = str(parent.get("run_id", ""))
        return run, events, external_parents


def _timestamps_conflict_with_sequence(events: list[dict[str, Any]]) -> bool:
    ordered = sorted(
        (
            event for event in events
            if isinstance(event.get("sequence_number"), int)
            and not isinstance(event.get("sequence_number"), bool)
            and event.get("timestamp") is not None
        ),
        key=lambda event: event["sequence_number"],
    )
    timestamps = [_timestamp_key(event["timestamp"]) for event in ordered]
    return any(left > right for left, right in zip(timestamps, timestamps[1:]))


def _timestamp_key(value: Any) -> float:
    if isinstance(value, datetime):
        normalized = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
        return normalized.timestamp()
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0
