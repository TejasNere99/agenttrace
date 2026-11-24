from datetime import datetime
from enum import StrEnum

from pydantic import Field

from app.schemas.agent_run import RunStatus
from app.schemas.common import ApiSchema, ObjectIdString


class DemoScenario(StrEnum):
    successful_execution = "successful_execution"
    tool_failure = "tool_failure"
    wrong_tool_selection = "wrong_tool_selection"
    repeated_tool_calls = "repeated_tool_calls"
    error_with_recovery = "error_with_recovery"
    unrecovered_failure = "unrecovered_failure"


class DemoRunRequest(ApiSchema):
    project_id: ObjectIdString
    scenario: DemoScenario


class DemoRunResponse(ApiSchema):
    run_id: ObjectIdString
    project_id: ObjectIdString
    task: str
    scenario: DemoScenario
    status: RunStatus
    event_count: int = Field(ge=0)
    duration_ms: int = Field(ge=0)
    duration_kind: str = "wall_clock"
    synthetic: bool = True
    started_at: datetime
    ended_at: datetime


class RunSummary(ApiSchema):
    run_id: ObjectIdString
    status: RunStatus
    event_count: int = Field(ge=0)
    successful_event_count: int = Field(ge=0)
    failed_event_count: int = Field(ge=0)
    tool_call_count: int = Field(ge=0)
    error_count: int = Field(ge=0)
    recovery_count: int = Field(ge=0)
    duration_ms: int | None = Field(default=None, ge=0)
    synthetic: bool
    scenario: str | None = None
