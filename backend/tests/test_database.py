import asyncio

from app.core.config import Settings
from app.core.database import DatabaseManager
from app.schemas.experiment import ExperimentCreate
from app.services.experiment_service import create_experiment
from app.utils.serialization import mongo_to_api
from tests.fakes import FakeDatabase


def test_mongo_object_id_serialization_is_recursive():
    from bson import ObjectId

    outer, inner = ObjectId(), ObjectId()
    document = {"_id": outer, "nested": {"reference": inner}, "values": [inner]}
    serialized = mongo_to_api(document)
    assert serialized == {"id": str(outer), "nested": {"reference": str(inner)}, "values": [str(inner)]}


def test_required_index_definitions_are_created():
    manager = DatabaseManager(Settings())
    database = FakeDatabase()
    manager.database = database
    asyncio.run(manager._ensure_indexes())
    assert len(database.projects.indexes) == 2
    assert [("project_id", 1), ("started_at", -1)] in database.agent_runs.indexes
    assert [("run_id", 1), ("sequence_number", 1)] in database.trace_events.indexes
    assert [("run_id", 1), ("metric_name", 1)] in database.evaluations.indexes
    assert [("created_at", -1)] in database.experiments.indexes


def test_experiment_rejects_invalid_run_reference(database):
    from bson import ObjectId
    from fastapi import HTTPException

    with __import__("pytest").raises(HTTPException) as error:
        asyncio.run(create_experiment(database, name="Control", description=None, run_ids=[str(ObjectId())]))
    assert error.value.status_code == 404


def test_experiment_schema_checks_object_id_shape_and_duplicates():
    from bson import ObjectId
    import pytest
    from pydantic import ValidationError

    valid_id = str(ObjectId())
    assert ExperimentCreate(name="  Study  ", run_ids=[valid_id]).name == "Study"
    with pytest.raises(ValidationError):
        ExperimentCreate(name="", run_ids=["invalid"])
    with pytest.raises(ValidationError):
        ExperimentCreate(name="Test", run_ids=[valid_id, valid_id])


def test_trace_event_schema_validates_enums_sequence_and_duration():
    from datetime import datetime, timezone
    import pytest
    from bson import ObjectId
    from pydantic import ValidationError
    from app.schemas.trace_event import TraceEventCreate

    base = {
        "run_id": str(ObjectId()), "sequence_number": 1, "event_type": "tool_call",
        "name": "Query source", "timestamp": datetime.now(timezone.utc),
        "inputs": ["source-a", {"limit": 5}],
    }
    event = TraceEventCreate(**base)
    assert event.inputs[1] == {"limit": 5}
    with pytest.raises(ValidationError):
        TraceEventCreate(**{**base, "timestamp": datetime.now()})
    for invalid in (
        {**base, "sequence_number": 0},
        {**base, "event_type": "made_up"},
        {**base, "status": "done"},
        {**base, "duration_ms": -1},
    ):
        with pytest.raises(ValidationError):
            TraceEventCreate(**invalid)


def test_database_integration_is_optional_when_uri_is_not_configured():
    # A live MongoDB integration check belongs in developer environments with an explicit test URI.
    import os
    import pytest

    if not os.getenv("MONGODB_TEST_URI"):
        pytest.skip("Set MONGODB_TEST_URI to run isolated MongoDB connectivity integration checks.")
    from pymongo import AsyncMongoClient

    async def ping() -> None:
        client = AsyncMongoClient(os.environ["MONGODB_TEST_URI"], serverSelectionTimeoutMS=2500)
        try:
            await client.admin.command("ping")
        finally:
            await client.close()

    asyncio.run(ping())
