from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from bson import ObjectId

from app.agents.scenarios import EventSpec
from app.schemas.demo import DemoScenario


class EventFactory:
    """Creates event IDs and resolves dependency keys to already-issued event IDs."""

    def __init__(self, run_id: str, scenario: DemoScenario) -> None:
        self.run_id = run_id
        self.scenario = scenario
        self._event_ids: dict[str, str] = {}

    def create(self, spec: EventSpec) -> dict[str, Any]:
        parent_event_id = None
        if spec.parent is not None:
            try:
                parent_event_id = self._event_ids[spec.parent]
            except KeyError as exc:
                raise ValueError("Scenario parent must reference an event already created in this run") from exc

        event_id = str(ObjectId())
        self._event_ids[spec.key] = event_id
        metadata = {
            "synthetic": True,
            "source": "agenttrace_demo_agent",
            "scenario": self.scenario.value,
        }
        metadata.update(deepcopy(spec.metadata or {}))
        return {
            "event_id": event_id,
            "run_id": self.run_id,
            "parent_event_id": parent_event_id,
            "sequence_number": 1,
            "event_type": spec.event_type.value,
            "name": spec.name,
            "status": spec.status.value,
            "inputs": deepcopy(spec.inputs),
            "outputs": deepcopy(spec.outputs),
            "error": deepcopy(spec.error),
            "timestamp": datetime.now(timezone.utc),
            "duration_ms": None,
            "metadata": metadata,
        }
