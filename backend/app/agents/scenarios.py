from dataclasses import dataclass
from typing import Any

from app.schemas.agent_run import RunStatus
from app.schemas.demo import DemoScenario
from app.schemas.trace_event import TraceEventStatus, TraceEventType


@dataclass(frozen=True)
class EventSpec:
    key: str
    event_type: TraceEventType
    name: str
    status: TraceEventStatus
    parent: str | None
    inputs: Any
    outputs: Any
    error: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class ScenarioDefinition:
    scenario: DemoScenario
    task: str
    expected_status: RunStatus
    description: str
    expected_outcome: str
    events: tuple[EventSpec, ...]


def _step(
    key: str,
    event_type: TraceEventType,
    name: str,
    status: TraceEventStatus,
    parent: str | None,
    inputs: Any,
    outputs: Any,
    *,
    error: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> EventSpec:
    return EventSpec(key, event_type, name, status, parent, inputs, outputs, error, metadata)


SCENARIOS: dict[DemoScenario, ScenarioDefinition] = {
    DemoScenario.successful_execution: ScenarioDefinition(
        scenario=DemoScenario.successful_execution,
        task="Analyze a small dataset and generate a summary.",
        expected_status=RunStatus.success,
        description="A deterministic synthetic task completes successfully.",
        expected_outcome="task_completed",
        events=(
            _step("start", TraceEventType.task_start, "Task Started", TraceEventStatus.success, None, {"prompt": "Analyze a small dataset and generate a summary."}, {"accepted": True}),
            _step("plan", TraceEventType.planning, "Plan Analysis", TraceEventStatus.success, "start", {}, {"steps": ["load dataset", "compute totals", "summarize"]}),
            _step("llm", TraceEventType.llm_call, "Draft Analysis Plan", TraceEventStatus.success, "plan", {"provider": "synthetic"}, {"plan": "Aggregate the sample values and compare groups."}),
            _step("tool", TraceEventType.tool_call, "Load Sample Dataset", TraceEventStatus.success, "llm", {"tool_name": "sample_dataset", "dataset": "quarterly_sales"}, {"call_id": "demo-sales-query"}),
            _step("result", TraceEventType.tool_result, "Dataset Returned", TraceEventStatus.success, "tool", {}, {"rows": 4, "values": [12, 18, 16, 22]}),
            _step("analysis", TraceEventType.code_execution, "Aggregate Dataset", TraceEventStatus.success, "result", {"operation": "sum_and_average"}, {"sum": 68, "average": 17}),
            _step("complete", TraceEventType.task_complete, "Summary Generated", TraceEventStatus.success, "analysis", {}, {"summary": "The sample totals 68, with an average of 17."}),
        ),
    ),
    DemoScenario.tool_failure: ScenarioDefinition(
        scenario=DemoScenario.tool_failure,
        task="Fetch a report from an unavailable sample endpoint.",
        expected_status=RunStatus.failed,
        description="A synthetic tool call fails and the task cannot complete.",
        expected_outcome="tool_error_without_recovery",
        events=(
            _step("start", TraceEventType.task_start, "Task Started", TraceEventStatus.success, None, {"prompt": "Fetch the latest report."}, {"accepted": True}),
            _step("plan", TraceEventType.planning, "Plan Report Retrieval", TraceEventStatus.success, "start", {}, {"steps": ["request report", "summarize"]}),
            _step("tool", TraceEventType.tool_call, "Request Report", TraceEventStatus.success, "plan", {"tool_name": "report_api", "report_id": "sample-404"}, {"call_id": "demo-report-request"}),
            _step("error", TraceEventType.error, "Report Service Error", TraceEventStatus.failed, "tool", {}, {}, error={"code": "DEMO_TOOL_UNAVAILABLE", "message": "The synthetic report service is unavailable.", "classification": "tool_error"}),
            _step("complete", TraceEventType.task_complete, "Task Failed", TraceEventStatus.failed, "error", {}, {"completed": False}),
        ),
    ),
    DemoScenario.wrong_tool_selection: ScenarioDefinition(
        scenario=DemoScenario.wrong_tool_selection,
        task="Calculate the mean of four sample values.",
        expected_status=RunStatus.failed,
        description="A synthetic example records an inappropriate tool choice.",
        expected_outcome="inappropriate_tool_selected",
        events=(
            _step("start", TraceEventType.task_start, "Task Started", TraceEventStatus.success, None, {"prompt": "Calculate the mean of [4, 8, 10, 14]."}, {"accepted": True}),
            _step("plan", TraceEventType.planning, "Plan Calculation", TraceEventStatus.success, "start", {}, {"steps": ["select calculation tool", "verify result"]}),
            _step("tool", TraceEventType.tool_call, "Select Web Search", TraceEventStatus.success, "plan", {"tool_name": "web_search", "intended_operation": "calculate_mean"}, {"call_id": "demo-wrong-tool"}, metadata={"selection_label": "synthetic_inappropriate_choice"}),
            _step("result", TraceEventType.tool_result, "Search Results Returned", TraceEventStatus.success, "tool", {}, {"results": ["A page describing averages."]}),
            _step("validation", TraceEventType.validation, "Validate Calculation Output", TraceEventStatus.failed, "result", {"expected": "numeric_mean"}, {"valid": False}),
            _step("error", TraceEventType.error, "Expected Numeric Result Missing", TraceEventStatus.failed, "validation", {}, {}, error={"code": "DEMO_EXPECTED_OUTPUT_MISSING", "message": "This synthetic scenario selected a tool that did not calculate the requested mean.", "classification": "illustrative_scenario"}, metadata={"expected_outcome": "inappropriate_tool_selected", "not_a_detected_reasoning_finding": True}),
            _step("complete", TraceEventType.task_complete, "Task Failed", TraceEventStatus.failed, "error", {}, {"completed": False}),
        ),
    ),
    DemoScenario.repeated_tool_calls: ScenarioDefinition(
        scenario=DemoScenario.repeated_tool_calls,
        task="Retrieve the same sample inventory twice.",
        expected_status=RunStatus.success,
        description="A deterministic synthetic trace contains two equivalent tool calls.",
        expected_outcome="task_completed_with_repeated_call_example",
        events=(
            _step("start", TraceEventType.task_start, "Task Started", TraceEventStatus.success, None, {"prompt": "Read the sample inventory."}, {"accepted": True}),
            _step("plan", TraceEventType.planning, "Plan Inventory Read", TraceEventStatus.success, "start", {}, {"steps": ["read inventory", "summarize count"]}),
            _step("tool1", TraceEventType.tool_call, "Read Inventory", TraceEventStatus.success, "plan", {"tool_name": "inventory_lookup", "warehouse": "sample"}, {"call_id": "demo-inventory-1"}, metadata={"repeat_group": "inventory_lookup", "repeat_index": 1}),
            _step("result1", TraceEventType.tool_result, "Inventory Returned", TraceEventStatus.success, "tool1", {}, {"items": 24}, metadata={"repeat_group": "inventory_lookup", "repeat_index": 1}),
            _step("tool2", TraceEventType.tool_call, "Read Inventory Again", TraceEventStatus.success, "result1", {"tool_name": "inventory_lookup", "warehouse": "sample"}, {"call_id": "demo-inventory-2"}, metadata={"repeat_group": "inventory_lookup", "repeat_index": 2, "repeats_prior_call": True}),
            _step("result2", TraceEventType.tool_result, "Inventory Returned Again", TraceEventStatus.success, "tool2", {}, {"items": 24}, metadata={"repeat_group": "inventory_lookup", "repeat_index": 2}),
            _step("validation", TraceEventType.validation, "Validate Inventory Count", TraceEventStatus.success, "result2", {"expected_type": "integer"}, {"valid": True}),
            _step("complete", TraceEventType.task_complete, "Inventory Summary Generated", TraceEventStatus.success, "validation", {}, {"summary": "24 sample items are in inventory."}),
        ),
    ),
    DemoScenario.error_with_recovery: ScenarioDefinition(
        scenario=DemoScenario.error_with_recovery,
        task="Fetch a report, recover from a timeout, and summarize it.",
        expected_status=RunStatus.success,
        description="A synthetic tool timeout is followed by explicit recovery and completion.",
        expected_outcome="recovered_and_completed",
        events=(
            _step("start", TraceEventType.task_start, "Task Started", TraceEventStatus.success, None, {"prompt": "Fetch and summarize report 24."}, {"accepted": True}),
            _step("plan", TraceEventType.planning, "Plan Report Retrieval", TraceEventStatus.success, "start", {}, {"steps": ["request report", "retry once", "summarize"]}),
            _step("tool1", TraceEventType.tool_call, "Request Report", TraceEventStatus.success, "plan", {"tool_name": "report_api", "attempt": 1}, {"call_id": "demo-report-1"}),
            _step("error", TraceEventType.error, "Report Request Timed Out", TraceEventStatus.failed, "tool1", {}, {}, error={"code": "DEMO_TIMEOUT", "message": "The first synthetic request timed out.", "classification": "tool_error"}),
            _step("recovery", TraceEventType.recovery, "Retry with Cached Endpoint", TraceEventStatus.success, "error", {"strategy": "retry_alternate_sample"}, {"recovered": True}),
            _step("tool2", TraceEventType.tool_call, "Retry Report Request", TraceEventStatus.success, "recovery", {"tool_name": "report_api", "attempt": 2}, {"call_id": "demo-report-2"}),
            _step("result", TraceEventType.tool_result, "Report Returned", TraceEventStatus.success, "tool2", {}, {"report_id": "24", "status": "ready"}),
            _step("validation", TraceEventType.validation, "Validate Report", TraceEventStatus.success, "result", {"required_fields": ["report_id", "status"]}, {"valid": True}),
            _step("complete", TraceEventType.task_complete, "Report Summary Generated", TraceEventStatus.success, "validation", {}, {"summary": "Report 24 is ready."}),
        ),
    ),
    DemoScenario.unrecovered_failure: ScenarioDefinition(
        scenario=DemoScenario.unrecovered_failure,
        task="Fetch a report when the sample service remains unavailable.",
        expected_status=RunStatus.failed,
        description="A synthetic tool error remains unresolved through task completion.",
        expected_outcome="failed_without_recovery",
        events=(
            _step("start", TraceEventType.task_start, "Task Started", TraceEventStatus.success, None, {"prompt": "Fetch report 99."}, {"accepted": True}),
            _step("plan", TraceEventType.planning, "Plan Report Retrieval", TraceEventStatus.success, "start", {}, {"steps": ["request report", "validate response"]}),
            _step("tool", TraceEventType.tool_call, "Request Report", TraceEventStatus.success, "plan", {"tool_name": "report_api", "report_id": "99"}, {"call_id": "demo-report-99"}),
            _step("error", TraceEventType.error, "Report Service Unavailable", TraceEventStatus.failed, "tool", {}, {}, error={"code": "DEMO_SERVICE_UNAVAILABLE", "message": "The synthetic report service remained unavailable.", "classification": "tool_error"}),
            _step("validation", TraceEventType.validation, "Validate Report Result", TraceEventStatus.failed, "error", {"required": "report data"}, {"valid": False}),
            _step("complete", TraceEventType.task_complete, "Task Failed", TraceEventStatus.failed, "validation", {}, {"completed": False}),
        ),
    ),
}
