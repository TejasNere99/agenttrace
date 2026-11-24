from datetime import datetime
from typing import Any, Literal, TypedDict

from bson import ObjectId

RunStatusValue = Literal["pending", "running", "success", "failed", "cancelled"]


class AgentRunDocument(TypedDict):
    _id: ObjectId
    project_id: str
    task: str
    agent_name: str
    status: RunStatusValue
    started_at: datetime | None
    ended_at: datetime | None
    duration_ms: int | None
    event_count: int
    synthetic: bool
    scenario: str | None
    failure_reason: str | None
    metadata: dict[str, Any]
    created_at: datetime
