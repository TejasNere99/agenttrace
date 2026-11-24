import logging
from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from fastapi import HTTPException
from pymongo.errors import PyMongoError

from app.schemas.agent_run import RunStatus
from app.services.project_service import parse_object_id

logger = logging.getLogger("agenttrace.run_manager")


class RunManager:
    """Creates runs and enforces the pending -> running -> terminal lifecycle."""

    def __init__(self, database: Any) -> None:
        self.database = database

    async def create_run(
        self,
        *,
        project_id: str,
        task: str,
        agent_name: str,
        synthetic: bool = False,
        scenario: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        project_object_id = parse_object_id(project_id)
        project = await self.database.projects.find_one({"_id": project_object_id}, {"_id": 1})
        if project is None:
            raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Project was not found."})

        run_id = ObjectId()
        document = {
            "_id": run_id,
            "project_id": str(project_object_id),
            "task": task,
            "agent_name": agent_name,
            "status": RunStatus.pending.value,
            "started_at": None,
            "ended_at": None,
            "duration_ms": None,
            "event_count": 0,
            "synthetic": synthetic,
            "scenario": scenario,
            "failure_reason": None,
            "metadata": metadata or {},
            "created_at": datetime.now(timezone.utc),
        }
        await self.database.agent_runs.insert_one(document)
        return str(run_id), document

    async def start_run(self, run_id: str) -> datetime:
        started_at = datetime.now(timezone.utc)
        result = await self.database.agent_runs.update_one(
            {"_id": parse_object_id(run_id), "status": RunStatus.pending.value},
            {"$set": {"status": RunStatus.running.value, "started_at": started_at}},
        )
        if result.matched_count != 1:
            raise HTTPException(status_code=409, detail={"code": "invalid_run_transition", "message": "Only a pending run can be started."})
        return started_at

    async def finish_run(
        self,
        run_id: str,
        *,
        status: RunStatus,
        duration_ms: int,
        event_count: int,
        failure_reason: str | None = None,
    ) -> dict[str, Any]:
        if status not in (RunStatus.success, RunStatus.failed):
            raise ValueError("A completed execution must finish with success or failed status")
        result = await self.database.agent_runs.update_one(
            {"_id": parse_object_id(run_id), "status": RunStatus.running.value},
            {
                "$set": {
                    "status": status.value,
                    "ended_at": datetime.now(timezone.utc),
                    "duration_ms": max(0, duration_ms),
                    "event_count": event_count,
                    "failure_reason": failure_reason,
                }
            },
        )
        if result.matched_count != 1:
            raise HTTPException(status_code=409, detail={"code": "invalid_run_transition", "message": "Only a running run can be completed."})
        return await self.database.agent_runs.find_one({"_id": parse_object_id(run_id)})

    async def fail_run(self, run_id: str, *, duration_ms: int, reason: str) -> None:
        """Best-effort failure finalization; preserve the original pipeline error."""
        try:
            object_id = parse_object_id(run_id)
            event_count = await self.database.trace_events.count_documents({"run_id": str(object_id)})
            await self.database.agent_runs.update_one(
                {"_id": object_id, "status": {"$in": [RunStatus.pending.value, RunStatus.running.value]}},
                {
                    "$set": {
                        "status": RunStatus.failed.value,
                        "ended_at": datetime.now(timezone.utc),
                        "duration_ms": max(0, duration_ms),
                        "event_count": event_count,
                        "failure_reason": reason,
                        "metadata.persistence_state": "partial" if event_count else "failed",
                    }
                },
            )
        except PyMongoError as exc:
            logger.error("Could not finalize a failed run (%s)", type(exc).__name__)
