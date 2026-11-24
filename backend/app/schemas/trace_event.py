from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import Field, field_validator, model_validator

from app.schemas.common import ApiSchema, ObjectIdString, normalize_utc_datetime


class TraceEventType(StrEnum):
    task_start = "task_start"
    planning = "planning"
    llm_call = "llm_call"
    tool_call = "tool_call"
    tool_result = "tool_result"
    code_execution = "code_execution"
    validation = "validation"
    error = "error"
    recovery = "recovery"
    task_complete = "task_complete"


class TraceEventStatus(StrEnum):
    pending = "pending"
    running = "running"
    success = "success"
    failed = "failed"
    skipped = "skipped"


class TraceEventCreate(ApiSchema):
    event_id: ObjectIdString | None = None
    run_id: ObjectIdString
    parent_event_id: ObjectIdString | None = None
    sequence_number: int = Field(gt=0)
    event_type: TraceEventType
    name: str = Field(min_length=1, max_length=300)
    status: TraceEventStatus = TraceEventStatus.pending
    inputs: Any = Field(default_factory=dict)
    outputs: Any = Field(default_factory=dict)
    error: dict[str, Any] | str | None = None
    timestamp: datetime
    duration_ms: int | None = Field(default=None, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("timestamp")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        return normalize_utc_datetime(value)


class TraceEventResponse(ApiSchema):
    id: ObjectIdString
    event_id: ObjectIdString
    run_id: ObjectIdString
    parent_event_id: ObjectIdString | None = None
    sequence_number: int = Field(gt=0)
    event_type: TraceEventType
    name: str
    status: TraceEventStatus
    inputs: Any = Field(default_factory=dict)
    outputs: Any = Field(default_factory=dict)
    error: dict[str, Any] | str | None = None
    timestamp: datetime
    duration_ms: int | None = Field(default=None, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def mirror_mongo_id_as_event_id(cls, value: Any) -> Any:
        if isinstance(value, dict) and "event_id" not in value and value.get("id") is not None:
            return {**value, "event_id": value["id"]}
        return value
