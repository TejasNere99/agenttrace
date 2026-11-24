import asyncio
import os
import uuid
from datetime import datetime, timezone

import pytest
from bson import ObjectId
from fastapi.testclient import TestClient
from pydantic import ValidationError
from pymongo import AsyncMongoClient
from pymongo.errors import PyMongoError

from app.agents.demo_agent import DemoAgent
from app.core.config import Settings
from app.main import create_app
from app.schemas.agent_run import RunStatus
from app.schemas.demo import DemoScenario
from app.services.event_persistence import EventPersistence
from app.tracing.collector import TraceCollector
from app.tracing.processor import TraceProcessor


@pytest.mark.parametrize(
    ("scenario", "expected_status", "expected_count"),
    [
        (DemoScenario.successful_execution, RunStatus.success, 7),
        (DemoScenario.tool_failure, RunStatus.failed, 5),
        (DemoScenario.wrong_tool_selection, RunStatus.failed, 7),
        (DemoScenario.repeated_tool_calls, RunStatus.success, 8),
        (DemoScenario.error_with_recovery, RunStatus.success, 9),
        (DemoScenario.unrecovered_failure, RunStatus.failed, 6),
    ],
)
def test_demo_agent_scenarios_produce_ordered_valid_event_documents(scenario, expected_status, expected_count):
    run_id = str(ObjectId())
    execution = DemoAgent().execute(scenario, run_id)
    collector = TraceCollector(run_id)
    captured = collector.capture_many(list(execution.events))
    documents = TraceProcessor().process(run_id, captured)

    assert execution.expected_status == expected_status
    assert len(documents) == expected_count
    assert [event["sequence_number"] for event in documents] == list(range(1, expected_count + 1))
    ids = {str(event["_id"]) for event in documents}
    assert all(event["run_id"] == run_id for event in documents)
    assert all(event["parent_event_id"] is None or event["parent_event_id"] in ids for event in documents)
    assert all(event["metadata"]["synthetic"] is True for event in documents)


def test_scenario_specific_expectations_are_explicit():
    run_id = str(ObjectId())
    wrong = DemoAgent().execute(DemoScenario.wrong_tool_selection, run_id)
    wrong_error = next(event for event in wrong.events if event["event_type"] == "error")
    assert wrong.expected_outcome == "inappropriate_tool_selected"
    assert wrong_error["metadata"]["not_a_detected_reasoning_finding"] is True

    repeated = DemoAgent().execute(DemoScenario.repeated_tool_calls, run_id)
    repeat_calls = [event for event in repeated.events if event["event_type"] == "tool_call"]
    assert len(repeat_calls) == 2
    assert repeat_calls[1]["metadata"]["repeats_prior_call"] is True

    recovery = DemoAgent().execute(DemoScenario.error_with_recovery, run_id)
    types = [event["event_type"] for event in recovery.events]
    assert "error" in types and "recovery" in types


def test_collector_rejects_invalid_events_and_cross_run_events():
    run_id = str(ObjectId())
    event = DemoAgent().execute(DemoScenario.successful_execution, run_id).events[0]
    collector = TraceCollector(run_id)
    with pytest.raises(ValidationError):
        collector.capture({**event, "event_type": "not_supported"})
    with pytest.raises(ValidationError):
        collector.capture({**event, "status": "done"})
    with pytest.raises(ValueError, match="different runs"):
        collector.capture({**event, "run_id": str(ObjectId())})


def test_processor_rejects_missing_parents_cross_run_and_cycles():
    run_id = str(ObjectId())
    events = DemoAgent().execute(DemoScenario.successful_execution, run_id).events
    collector = TraceCollector(run_id)
    captured = collector.capture_many(list(events))
    processor = TraceProcessor()

    invalid_parent = captured[1].model_copy(update={"parent_event_id": str(ObjectId())})
    with pytest.raises(ValueError, match="same run"):
        processor.process(run_id, [captured[0], invalid_parent])
    with pytest.raises(ValueError, match="another run"):
        processor.process(str(ObjectId()), list(captured))

    first, second = captured[:2]
    cycle = [
        first.model_copy(update={"parent_event_id": second.event_id}),
        second.model_copy(update={"parent_event_id": first.event_id}),
    ]
    with pytest.raises(ValueError, match="Circular"):
        processor.process(run_id, cycle)


def test_event_persistence_is_idempotent(database):
    run_id = str(ObjectId())
    execution = DemoAgent().execute(DemoScenario.tool_failure, run_id)
    documents = TraceProcessor().process(run_id, TraceCollector(run_id).capture_many(list(execution.events)))
    persistence = EventPersistence(database)
    first_count = asyncio.run(persistence.persist(run_id, documents))
    second_count = asyncio.run(persistence.persist(run_id, documents))
    assert first_count == second_count == len(documents)
    assert len(database.trace_events.documents) == len(documents)


def test_demo_api_persists_all_scenarios_and_computed_summaries(client):
    project = client.post("/api/projects", json={"name": "Scenario API tests"})
    assert project.status_code == 201
    project_id = project.json()["id"]
    expected = {
        "successful_execution": "success",
        "tool_failure": "failed",
        "wrong_tool_selection": "failed",
        "repeated_tool_calls": "success",
        "error_with_recovery": "success",
        "unrecovered_failure": "failed",
    }

    for scenario, final_status in expected.items():
        response = client.post("/api/demo/run", json={"project_id": project_id, "scenario": scenario})
        assert response.status_code == 201, response.text
        data = response.json()
        assert data["scenario"] == scenario
        assert data["status"] == final_status
        assert data["synthetic"] is True
        assert data["duration_kind"] == "actual_wall_clock"

        run = client.get(f"/api/runs/{data['run_id']}")
        assert run.status_code == 200
        assert run.json()["synthetic"] is True
        assert run.json()["event_count"] == data["event_count"]

        events = client.get(f"/api/runs/{data['run_id']}/events")
        assert events.status_code == 200
        assert [event["sequence_number"] for event in events.json()] == list(range(1, data["event_count"] + 1))
        assert all(event["event_id"] == event["id"] for event in events.json())

        summary = client.get(f"/api/runs/{data['run_id']}/summary")
        assert summary.status_code == 200
        summary_data = summary.json()
        assert summary_data["event_count"] == data["event_count"]
        assert summary_data["tool_call_count"] == sum(e["event_type"] == "tool_call" for e in events.json())
        assert summary_data["error_count"] == sum(e["event_type"] == "error" for e in events.json())
        assert summary_data["recovery_count"] == sum(e["event_type"] == "recovery" for e in events.json())
        assert summary_data["failed_event_count"] == sum(e["status"] == "failed" for e in events.json())


def test_demo_api_marks_run_failed_when_event_persistence_is_partial(client, manager):
    from tests.fakes import FakeCollection

    class FailsOnSecondWrite(FakeCollection):
        def __init__(self):
            super().__init__()
            self.write_count = 0

        async def update_one(self, query, update, upsert=False):
            self.write_count += 1
            if self.write_count == 2:
                raise PyMongoError("simulated write failure")
            return await super().update_one(query, update, upsert)

    trace_events = FailsOnSecondWrite()
    manager.database.collections["trace_events"] = trace_events
    project = client.post("/api/projects", json={"name": "Partial persistence test"})
    assert project.status_code == 201

    response = client.post(
        "/api/demo/run",
        json={"project_id": project.json()["id"], "scenario": "successful_execution"},
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "database_unavailable"

    run = manager.database.agent_runs.documents[-1]
    assert run["status"] == "failed"
    assert run["event_count"] == 1
    assert run["metadata"]["persistence_state"] == "partial"
    assert len(trace_events.documents) == 1


def test_demo_api_validation_missing_project_and_empty_manual_run(client):
    invalid_id = client.post("/api/demo/run", json={"project_id": "invalid", "scenario": "successful_execution"})
    assert invalid_id.status_code == 422

    missing = client.post("/api/demo/run", json={"project_id": str(ObjectId()), "scenario": "successful_execution"})
    assert missing.status_code == 404

    project = client.post("/api/projects", json={"name": "Manual pending run"}).json()
    invalid_scenario = client.post("/api/demo/run", json={"project_id": project["id"], "scenario": "hallucinated_scenario"})
    assert invalid_scenario.status_code == 422

    created = client.post("/api/runs", json={"project_id": project["id"], "task": "Await future execution", "agent_name": "Unstarted Agent"})
    assert created.status_code == 201
    run = created.json()
    assert run["status"] == "pending"
    assert run["started_at"] is None
    events = client.get(f"/api/runs/{run['id']}/events")
    assert events.status_code == 200 and events.json() == []
    summary = client.get(f"/api/runs/{run['id']}/summary")
    assert summary.json() == {
        "run_id": run["id"], "status": "pending", "event_count": 0,
        "successful_event_count": 0, "failed_event_count": 0, "tool_call_count": 0,
        "error_count": 0, "recovery_count": 0, "duration_ms": None,
        "synthetic": False, "scenario": None,
    }


def test_graph_and_debug_apis_cover_all_demo_scenarios(client):
    project = client.post("/api/projects", json={"name": "Graph analysis scenarios"}).json()
    expected = {
        "successful_execution": ("success", 0, False),
        "tool_failure": ("failed", 2, False),
        "wrong_tool_selection": ("failed", 3, False),
        "repeated_tool_calls": ("success", 0, False),
        "error_with_recovery": ("success", 1, True),
        "unrecovered_failure": ("failed", 3, False),
    }
    for scenario, (run_status, failures, recovered) in expected.items():
        created = client.post("/api/demo/run", json={"project_id": project["id"], "scenario": scenario})
        assert created.status_code == 201, created.text
        run_id = created.json()["run_id"]
        graph = client.get(f"/api/runs/{run_id}/graph")
        assert graph.status_code == 200, graph.text
        assert graph.json()["graph_valid"] is True
        assert graph.json()["statistics"]["node_count"] == created.json()["event_count"]
        assert graph.json()["statistics"]["edge_count"] == created.json()["event_count"] - 1

        debug = client.get(f"/api/runs/{run_id}/debug")
        assert debug.status_code == 200, debug.text
        data = debug.json()
        assert data["run_status"] == run_status
        assert data["failure_analysis"]["total_failure_events"] == failures
        assert data["propagation_analysis"]["recovered"] is recovered
        if scenario == "wrong_tool_selection":
            assert all(record["failure_category"] != "tool_failure" for record in data["failure_analysis"]["failure_records"])


def test_graph_debug_validation_empty_trace_and_invalid_graph(client, database):
    invalid_id = "not-an-object-id"
    assert client.get(f"/api/runs/{invalid_id}/graph").status_code == 400
    assert client.get(f"/api/runs/{invalid_id}/debug").status_code == 400
    assert client.get(f"/api/runs/{str(ObjectId())}/graph").status_code == 404

    project = client.post("/api/projects", json={"name": "Graph validation API"}).json()
    empty = client.post("/api/runs", json={"project_id": project["id"], "task": "empty", "agent_name": "test"}).json()
    graph = client.get(f"/api/runs/{empty['id']}/graph").json()
    assert graph["graph_valid"] is True and graph["nodes"] == [] and graph["statistics"]["max_depth"] == 0
    debug = client.get(f"/api/runs/{empty['id']}/debug").json()
    assert debug["failure_analysis"]["failure_detected"] is False
    assert "No trace events" in debug["limitations"][0]

    run = client.post("/api/runs", json={"project_id": project["id"], "task": "malformed", "agent_name": "test"}).json()
    first_id, second_id = ObjectId(), ObjectId()
    asyncio.run(database.trace_events.insert_one({
        "_id": first_id, "run_id": run["id"], "parent_event_id": str(second_id),
        "sequence_number": 1, "event_type": "planning", "name": "A", "status": "success",
        "timestamp": datetime.now(timezone.utc), "metadata": {},
    }))
    asyncio.run(database.trace_events.insert_one({
        "_id": second_id, "run_id": run["id"], "parent_event_id": str(first_id),
        "sequence_number": 2, "event_type": "planning", "name": "B", "status": "success",
        "timestamp": datetime.now(timezone.utc), "metadata": {},
    }))
    invalid_graph = client.get(f"/api/runs/{run['id']}/graph").json()
    assert invalid_graph["graph_valid"] is False
    assert "circular_dependency" in [issue["code"] for issue in invalid_graph["validation_issues"]]
    invalid_debug = client.get(f"/api/runs/{run['id']}/debug").json()
    assert invalid_debug["graph_summary"]["graph_valid"] is False


def test_live_mongodb_pipeline_uses_and_removes_only_an_isolated_database():
    uri = os.getenv("MONGODB_TEST_URI")
    database_name = os.getenv("MONGODB_TEST_DATABASE")
    if not uri or not database_name:
        pytest.skip("Set MONGODB_TEST_URI and MONGODB_TEST_DATABASE for isolated MongoDB persistence tests.")
    if not database_name.startswith("agenttrace_test_") or database_name == "agenttrace":
        pytest.fail("Live persistence tests require a dedicated agenttrace_test_* database name.")

    manager = None
    try:
        manager = __import__("app.core.database", fromlist=["DatabaseManager"]).DatabaseManager(
            Settings(mongodb_uri=uri, mongodb_database=database_name)
        )
        with TestClient(create_app(settings=Settings(mongodb_uri=uri, mongodb_database=database_name), database_manager=manager)) as live_client:
            project = live_client.post("/api/projects", json={"name": "Isolated integration fixture"})
            assert project.status_code == 201
            result = live_client.post("/api/demo/run", json={"project_id": project.json()["id"], "scenario": "error_with_recovery"})
            assert result.status_code == 201, result.text
            events = live_client.get(f"/api/runs/{result.json()['run_id']}/events")
            assert events.status_code == 200
            assert len(events.json()) == result.json()["event_count"]
            assert any(event["event_type"] == "recovery" for event in events.json())
            assert live_client.get(f"/api/runs/{result.json()['run_id']}/summary").json()["status"] == "success"
            graph = live_client.get(f"/api/runs/{result.json()['run_id']}/graph")
            assert graph.status_code == 200 and graph.json()["graph_valid"] is True
            assert graph.json()["statistics"]["node_count"] == len(events.json())
            debug = live_client.get(f"/api/runs/{result.json()['run_id']}/debug")
            assert debug.status_code == 200 and debug.json()["propagation_analysis"]["recovered"] is True
    finally:
        if manager is not None and manager.client is not None:
            asyncio.run(manager.close())

            async def cleanup_test_database() -> None:
                cleanup_client = AsyncMongoClient(uri, serverSelectionTimeoutMS=5000)
                try:
                    await cleanup_client.drop_database(database_name)
                finally:
                    await cleanup_client.close()

            asyncio.run(cleanup_test_database())
