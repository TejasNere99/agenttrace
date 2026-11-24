from datetime import datetime
from typing import Any, Literal, TypedDict

from bson import ObjectId

EventTypeValue = Literal[
    "task_start", "planning", "llm_call", "tool_call", "tool_result", "code_execution",
    "validation", "error", "recovery", "task_complete",
]
EventStatusValue = Literal["pending", "running", "success", "failed", "skipped"]


class TraceEventDocument(TypedDict):
    # MongoDB _id is also the event_id exposed by the API.
    _id: ObjectId
    run_id: str
    parent_event_id: str | None
    sequence_number: int
    event_type: EventTypeValue
    name: str
    status: EventStatusValue
    inputs: Any
    outputs: Any
    error: dict[str, Any] | str | None
    timestamp: datetime
    duration_ms: int | None
    metadata: dict[str, Any]
