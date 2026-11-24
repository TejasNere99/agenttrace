from datetime import datetime, timezone
from typing import Any

from bson import ObjectId


async def create_experiment(database: Any, *, name: str, description: str | None, run_ids: list[str]) -> dict[str, Any]:
    """Validate all referenced run IDs before storing an experiment definition."""
    object_ids = [ObjectId(run_id) for run_id in run_ids]
    if object_ids:
        found = await database.agent_runs.count_documents({"_id": {"$in": object_ids}})
        if found != len(object_ids):
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail={"code": "run_reference_not_found", "message": "One or more referenced runs were not found."})
    now = datetime.now(timezone.utc)
    document = {"name": name, "description": description, "run_ids": run_ids, "created_at": now, "updated_at": now}
    result = await database.experiments.insert_one(document)
    from app.utils.serialization import mongo_to_api

    document["_id"] = result.inserted_id
    return mongo_to_api(document) or {}
