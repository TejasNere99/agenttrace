from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from pymongo import DESCENDING

from app.utils.serialization import mongo_to_api


def parse_object_id(value: str) -> ObjectId:
    if not ObjectId.is_valid(value):
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail={"code": "invalid_id", "message": "Project ID must be a valid MongoDB ObjectId."})
    return ObjectId(value)


async def create_project(database: Any, payload: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    document = {
        "name": payload["name"],
        "description": payload.get("description"),
        "created_at": now,
        "updated_at": now,
    }
    result = await database.projects.insert_one(document)
    document["_id"] = result.inserted_id
    return mongo_to_api(document) or {}


async def list_projects(database: Any, *, skip: int, limit: int) -> list[dict[str, Any]]:
    cursor = database.projects.find({}).sort([("created_at", DESCENDING)]).skip(skip).limit(limit)
    return [mongo_to_api(document) or {} for document in await cursor.to_list(length=limit)]


async def get_project(database: Any, project_id: str) -> dict[str, Any]:
    document = await database.projects.find_one({"_id": parse_object_id(project_id)})
    if document is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Project was not found."})
    return mongo_to_api(document) or {}


async def update_project(database: Any, project_id: str, changes: dict[str, Any]) -> dict[str, Any]:
    object_id = parse_object_id(project_id)
    changes["updated_at"] = datetime.now(timezone.utc)
    result = await database.projects.update_one({"_id": object_id}, {"$set": changes})
    if result.matched_count == 0:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Project was not found."})
    document = await database.projects.find_one({"_id": object_id})
    return mongo_to_api(document) or {}


async def delete_project(database: Any, project_id: str) -> None:
    object_id = parse_object_id(project_id)
    project = await database.projects.find_one({"_id": object_id}, {"_id": 1})
    if project is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Project was not found."})
    has_runs = await database.agent_runs.find_one({"project_id": str(object_id)}, {"_id": 1})
    if has_runs is not None:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=409,
            detail={"code": "project_has_runs", "message": "Project must have no associated runs before it can be deleted."},
        )
    await database.projects.delete_one({"_id": object_id})
