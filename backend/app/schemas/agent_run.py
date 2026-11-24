from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import Field

from app.schemas.common import ApiSchema, ObjectIdString


class RunStatus(StrEnum):
    pending = "pending"
    running = "running"
    success = "success"
    failed = "failed"
    cancelled = "cancelled"


class AgentRunCreate(ApiSchema):
    project_id: ObjectIdString
    task: str = Field(min_length=1, max_length=5000)
    agent_name: str = Field(min_length=1, max_length=200)


class AgentRunResponse(ApiSchema):
    id: ObjectIdString
    project_id: ObjectIdString
    task: str
    agent_name: str
    status: RunStatus
    started_at: datetime | None = None
    ended_at: datetime | None = None
    duration_ms: int | None = Field(default=None, ge=0)
    event_count: int = Field(default=0, ge=0)
    synthetic: bool = False
    scenario: str | None = None
    failure_reason: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
