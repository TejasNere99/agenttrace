from dataclasses import dataclass
from typing import Any

from app.agents.scenarios import SCENARIOS
from app.schemas.agent_run import RunStatus
from app.schemas.demo import DemoScenario
from app.tracing.event_factory import EventFactory


@dataclass(frozen=True)
class DemoExecution:
    scenario: DemoScenario
    task: str
    expected_status: RunStatus
    description: str
    expected_outcome: str
    events: tuple[dict[str, Any], ...]


class DemoAgent:
    """Generates deterministic synthetic events; it has no database dependency."""

    agent_name = "AgentTrace Demo Agent"

    def execute(self, scenario: DemoScenario, run_id: str) -> DemoExecution:
        definition = SCENARIOS[scenario]
        factory = EventFactory(run_id, scenario)
        events = tuple(factory.create(spec) for spec in definition.events)
        return DemoExecution(
            scenario=definition.scenario,
            task=definition.task,
            expected_status=definition.expected_status,
            description=definition.description,
            expected_outcome=definition.expected_outcome,
            events=events,
        )
