from typing import Any

from bson import ObjectId
from fastapi import HTTPException

from app.schemas.common import validate_object_id
from app.services import run_service
from app.utils.serialization import mongo_to_api


class TraceRetrievalService:
    """Read stored runs, ordered events, and counts computed from persisted events."""

    def __init__(self, database: Any) -> None:
        self.database = database

    async def get_run(self, run_id: str) -> dict[str, Any]:
        return await run_service.get_run(self.database, run_id)

    async def get_events(self, run_id: str, *, skip: int = 0, limit: int = 1000) -> list[dict[str, Any]]:
        return await run_service.list_run_events(self.database, run_id, skip=skip, limit=limit)

    async def get_summary(self, run_id: str) -> dict[str, Any]:
        canonical_id = validate_object_id(run_id)
        object_id = ObjectId(canonical_id)
        run = await self.database.agent_runs.find_one({"_id": object_id})
        if run is None:
            raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Run was not found."})

        run_ref = str(object_id)
        events = self.database.trace_events
        event_count = await events.count_documents({"run_id": run_ref})
        successful = await events.count_documents({"run_id": run_ref, "status": "success"})
        failed = await events.count_documents({"run_id": run_ref, "status": "failed"})
        tool_calls = await events.count_documents({"run_id": run_ref, "event_type": "tool_call"})
        errors = await events.count_documents({"run_id": run_ref, "event_type": "error"})
        recoveries = await events.count_documents({"run_id": run_ref, "event_type": "recovery"})
        result = mongo_to_api(run) or {}
        return {
            "run_id": result["id"],
            "status": result["status"],
            "event_count": event_count,
            "successful_event_count": successful,
            "failed_event_count": failed,
            "tool_call_count": tool_calls,
            "error_count": errors,
            "recovery_count": recoveries,
            "duration_ms": result.get("duration_ms"),
            "synthetic": result.get("synthetic", False),
            "scenario": result.get("scenario"),
        }
