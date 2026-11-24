from typing import Any

from pymongo import ASCENDING, DESCENDING

from app.services.project_service import parse_object_id
from app.utils.serialization import mongo_to_api


async def list_runs(
    database: Any,
    *,
    skip: int,
    limit: int,
    project_id: str | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    filters: dict[str, Any] = {}
    if project_id is not None:
        # Validate the external identifier before using the string reference in a query.
        filters["project_id"] = str(parse_object_id(project_id))
    if status is not None:
        filters["status"] = status
    cursor = database.agent_runs.find(filters).sort([("started_at", DESCENDING), ("_id", DESCENDING)]).skip(skip).limit(limit)
    return [mongo_to_api(document) or {} for document in await cursor.to_list(length=limit)]


async def get_run(database: Any, run_id: str) -> dict[str, Any]:
    document = await database.agent_runs.find_one({"_id": parse_object_id(run_id)})
    if document is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Run was not found."})
    return mongo_to_api(document) or {}


async def list_run_events(database: Any, run_id: str, *, skip: int, limit: int) -> list[dict[str, Any]]:
    object_id = parse_object_id(run_id)
    run = await database.agent_runs.find_one({"_id": object_id}, {"_id": 1})
    if run is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Run was not found."})
    cursor = (
        database.trace_events.find({"run_id": str(object_id)})
        .sort([("sequence_number", ASCENDING), ("_id", ASCENDING)])
        .skip(skip)
        .limit(limit)
    )
    return [mongo_to_api(document) or {} for document in await cursor.to_list(length=limit)]
