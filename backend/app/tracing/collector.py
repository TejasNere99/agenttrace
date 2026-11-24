from collections.abc import Mapping
from typing import Any

from bson import ObjectId
from app.schemas.common import validate_object_id
from app.schemas.trace_event import TraceEventCreate


class TraceCollector:
    """Validates, run-scopes, and retains events before processing."""

    def __init__(self, run_id: str) -> None:
        self.run_id = validate_object_id(run_id)
        self._events: list[TraceEventCreate] = []
        self._event_ids: set[str] = set()

    @property
    def events(self) -> tuple[TraceEventCreate, ...]:
        return tuple(self._events)

    def capture(self, raw_event: Mapping[str, Any]) -> TraceEventCreate:
        payload = dict(raw_event)
        event_run_id = validate_object_id(payload.get("run_id"))
        if event_run_id != self.run_id:
            raise ValueError("TraceCollector cannot mix events from different runs")
        payload["run_id"] = event_run_id
        payload.setdefault("event_id", str(ObjectId()))
        payload.setdefault("sequence_number", len(self._events) + 1)
        event = TraceEventCreate.model_validate(payload)
        if event.event_id is None:
            raise ValueError("Trace event ID could not be assigned")
        if event.event_id in self._event_ids:
            raise ValueError("Duplicate event ID in one run")
        self._event_ids.add(event.event_id)
        self._events.append(event)
        return event

    def capture_many(self, raw_events: list[Mapping[str, Any]]) -> tuple[TraceEventCreate, ...]:
        for raw_event in raw_events:
            self.capture(raw_event)
        return self.events
