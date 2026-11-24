from datetime import datetime, timezone

import networkx as nx
from bson import ObjectId

from app.debugging.failure_detector import FailureDetector
from app.debugging.propagation_analyzer import PropagationAnalyzer
from app.graph.graph_builder import GraphBuilder
from app.graph.graph_serializer import GraphSerializer


def event(event_id, sequence, *, parent=None, status="success", event_type="planning", run_id="run-1", error=None, name=None):
    return {
        "_id": event_id,
        "run_id": run_id,
        "parent_event_id": parent,
        "sequence_number": sequence,
        "event_type": event_type,
        "name": name or f"Event {sequence}",
        "status": status,
        "timestamp": datetime(2026, 1, 1, 0, 0, sequence, tzinfo=timezone.utc),
        "duration_ms": 5,
        "error": error,
        "metadata": {"synthetic": True, "label": "sample"},
    }


def test_empty_single_node_and_linear_graph_statistics():
    builder = GraphBuilder()
    empty = builder.build("run-1", [])
    assert empty.graph_valid
    assert empty.statistics["max_depth"] == 0
    assert empty.statistics["root_count"] == empty.statistics["leaf_count"] == 0

    single = builder.build("run-1", [event("a", 1)])
    assert single.statistics["node_count"] == 1
    assert single.statistics["edge_count"] == 0
    assert single.statistics["roots"] == single.statistics["leaves"] == ["a"]

    chain = builder.build("run-1", [event("a", 1), event("b", 2, parent="a"), event("c", 3, parent="b")])
    assert chain.graph_valid
    assert chain.statistics["edge_count"] == 2
    assert chain.statistics["max_depth"] == 2
    assert chain.topological_order == ["a", "b", "c"]


def test_branching_multiple_roots_leaves_and_serializer_contract():
    result = GraphBuilder().build("run-1", [
        event("a", 1), event("b", 2, parent="a"), event("c", 3, parent="a"),
        event("d", 4), event("e", 5, parent="d"),
    ])
    assert result.statistics["root_count"] == 2
    assert result.statistics["leaf_count"] == 3
    assert result.statistics["branching_points"] == ["a"]
    assert result.statistics["disconnected_component_count"] == 2
    assert result.statistics["max_depth"] == 1
    serialized = GraphSerializer().serialize(result)
    assert [node["id"] for node in serialized["nodes"]] == ["a", "b", "c", "d", "e"]
    assert serialized["edges"][0]["source"] == "a"
    assert serialized["nodes"][0]["data"]["status"] == "success"


def test_missing_self_duplicate_cross_run_and_cycle_are_reported():
    builder = GraphBuilder()
    missing = builder.build("run-1", [event("child", 2, parent="absent")])
    assert not missing.graph_valid
    assert missing.validation_issues[0]["code"] == "missing_parent_reference"

    self_ref = builder.build("run-1", [event("self", 1, parent="self")])
    assert "self_reference" in [issue["code"] for issue in self_ref.validation_issues]

    cyclic = builder.build("run-1", [event("a", 1, parent="b"), event("b", 2, parent="a")])
    assert not nx.is_directed_acyclic_graph(cyclic.graph)
    assert "circular_dependency" in [issue["code"] for issue in cyclic.validation_issues]
    assert cyclic.topological_order == []

    cross = builder.build("run-1", [event("child", 2, parent="outside")], external_parent_run_ids={"outside": "run-2"})
    assert "cross_run_reference" in [issue["code"] for issue in cross.validation_issues]

    duplicate = builder.build("run-1", [event("same", 1), event("same", 2)])
    assert "duplicate_event_id" in [issue["code"] for issue in duplicate.validation_issues]


def test_failure_detector_deduplicates_signals_and_orders_by_sequence():
    events = [
        event("late", 4, status="failed", event_type="error", error={"message": "later"}),
        event("early", 2, status="failed", event_type="validation", error={"classification": "validation_error", "message": "invalid"}),
        event("ok", 1),
    ]
    analysis = FailureDetector().detect(events, run_status="failed")
    assert analysis["total_failure_events"] == 2
    assert analysis["first_detected_failure"]["event_id"] == "early"
    assert analysis["first_detected_failure"]["failure_category"] == "validation_failure"
    assert analysis["failure_records"][1]["failure_evidence"] == ["status=failed", "event_type=error", "structured_error_present"]


def test_failure_detector_classification_and_run_status_fallback():
    detector = FailureDetector()
    tool = detector.detect([event("tool", 1, status="failed", event_type="tool_result", error={"classification": "tool_error"})])
    assert tool["failure_records"][0]["failure_category"] == "tool_failure"
    unknown = detector.detect([event("unknown", 1, status="failed", event_type="code_execution")])
    assert unknown["failure_records"][0]["failure_category"] == "unknown_failure"
    run_only = detector.detect([], run_status="failed")
    assert run_only["failure_detected"] and run_only["total_failure_events"] == 0
    assert run_only["first_detected_failure"]["source"] == "run_status"


def test_propagation_handles_branches_overlapping_failures_statuses_and_recovery():
    events = [
        event("f1", 1, status="failed", event_type="error"),
        event("f2", 2, parent="f1", status="failed", event_type="validation"),
        event("ok", 3, parent="f1", status="success"),
        event("bad", 4, parent="f2", status="failed"),
        event("skip", 5, parent="f2", status="skipped"),
        event("unknown", 6, parent="f1", status="pending"),
        event("recovery", 7, parent="f2", status="success", event_type="recovery"),
        event("complete", 8, parent="recovery", status="success", event_type="task_complete"),
    ]
    result = GraphBuilder().build("run-1", events)
    failures = FailureDetector().detect(events)["failure_records"]
    analysis = PropagationAnalyzer().analyze(result, failures)
    assert analysis["directly_dependent_count"] == 6
    assert analysis["potentially_affected_count"] == 7
    assert analysis["completed_successfully_downstream_count"] >= 2
    assert analysis["failed_downstream_count"] == 2
    assert analysis["skipped_downstream_count"] == 1
    assert analysis["recovery_recorded"] and analysis["recovered"]
    assert len(next(item for item in analysis["downstream_events"] if item["event_id"] == "bad")["failure_event_ids"]) == 2


def test_propagation_empty_graph_is_safe():
    result = GraphBuilder().build("run-1", [])
    analysis = PropagationAnalyzer().analyze(result, [])
    assert analysis["potentially_affected_count"] == 0
    assert analysis["downstream_events"] == []
    assert not analysis["recovered"]


def test_ids_are_stable_for_objectid_documents():
    event_id = ObjectId()
    result = GraphBuilder().build("run-1", [event(event_id, 1)])
    assert list(result.graph.nodes) == [str(event_id)]
