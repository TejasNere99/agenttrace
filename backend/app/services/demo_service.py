import logging
from time import perf_counter_ns
from typing import Any

from app.agents.demo_agent import DemoAgent
from app.agents.scenarios import SCENARIOS
from app.schemas.demo import DemoRunRequest
from app.services.event_persistence import EventPersistence
from app.services.run_manager import RunManager
from app.tracing.collector import TraceCollector
from app.tracing.processor import TraceProcessor

logger = logging.getLogger("agenttrace.demo")


class DemoRunService:
    """Orchestrates run lifecycle, deterministic agent, trace pipeline, and persistence."""

    def __init__(self, database: Any) -> None:
        self.database = database
        self.run_manager = RunManager(database)
        self.agent = DemoAgent()
        self.processor = TraceProcessor()
        self.persistence = EventPersistence(database)

    async def execute(self, request: DemoRunRequest) -> dict[str, Any]:
        scenario = request.scenario
        # Build the pending run using only scenario metadata; the agent itself has no DB access.
        spec = SCENARIOS[scenario]
        run_id, _ = await self.run_manager.create_run(
            project_id=request.project_id,
            task=spec.task,
            agent_name=self.agent.agent_name,
            synthetic=True,
            scenario=scenario.value,
            metadata={
                "source": "agenttrace_demo_agent",
                "synthetic": True,
                "scenario_description": spec.description,
                "expected_outcome": spec.expected_outcome,
                "duration_kind": "actual_wall_clock",
            },
        )
        started_at = await self.run_manager.start_run(run_id)
        started_clock = perf_counter_ns()
        try:
            execution = self.agent.execute(scenario, run_id)
            collector = TraceCollector(run_id)
            captured = collector.capture_many(list(execution.events))
            documents = self.processor.process(run_id, captured)
            event_count = await self.persistence.persist(run_id, documents)
            if event_count != len(documents):
                raise RuntimeError("Persisted event count did not match the processed trace")

            duration_ms = (perf_counter_ns() - started_clock) // 1_000_000
            failure_reason = None
            if execution.expected_status.value == "failed":
                failure_reason = execution.expected_outcome
            finished = await self.run_manager.finish_run(
                run_id,
                status=execution.expected_status,
                duration_ms=duration_ms,
                event_count=event_count,
                failure_reason=failure_reason,
            )
            return {
                "run_id": run_id,
                "project_id": finished["project_id"],
                "task": finished["task"],
                "scenario": scenario.value,
                "status": finished["status"],
                "event_count": event_count,
                "duration_ms": finished["duration_ms"],
                "duration_kind": "actual_wall_clock",
                "synthetic": True,
                "started_at": finished["started_at"] or started_at,
                "ended_at": finished["ended_at"],
            }
        except Exception as exc:
            duration_ms = (perf_counter_ns() - started_clock) // 1_000_000
            logger.warning("Demo run pipeline failed (%s)", type(exc).__name__)
            await self.run_manager.fail_run(
                run_id,
                duration_ms=duration_ms,
                reason="Demo execution or event persistence failed; inspect the available trace events.",
            )
            raise
