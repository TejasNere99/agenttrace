from typing import Any

from bson import ObjectId
from pydantic import ValidationError

from app.schemas.common import validate_object_id
from app.schemas.trace_event import TraceEventCreate


class TraceProcessor:
    """Assigns canonical sequence numbers and validates same-run parent dependencies."""

    def process(self, run_id: str, events: tuple[TraceEventCreate, ...] | list[TraceEventCreate]) -> list[dict[str, Any]]:
        canonical_run_id = validate_object_id(run_id)
        prepared: list[TraceEventCreate] = []
        event_ids: set[str] = set()

        for sequence_number, original in enumerate(events, start=1):
            payload = original.model_dump(mode="python")
            if payload["run_id"] != canonical_run_id:
                raise ValueError("Trace processor cannot persist events from another run")
            if payload["event_id"] is None:
                raise ValueError("Every processed trace event must have an event ID")
            if payload["event_id"] in event_ids:
                raise ValueError("Trace contains duplicate event IDs")
            event_ids.add(payload["event_id"])
            payload["sequence_number"] = sequence_number
            prepared.append(TraceEventCreate.model_validate(payload))

        parents: dict[str, str | None] = {}
        for event in prepared:
            assert event.event_id is not None
            parent = event.parent_event_id
            if parent is not None and parent not in event_ids:
                raise ValueError("Every parent event ID must reference an event in the same run")
            if parent == event.event_id:
                raise ValueError("An event cannot depend on itself")
            parents[event.event_id] = parent

        for event_id in event_ids:
            visited: set[str] = set()
            current: str | None = event_id
            while current is not None:
                if current in visited:
                    raise ValueError("Circular trace event dependencies are not allowed")
                visited.add(current)
                current = parents[current]

        documents: list[dict[str, Any]] = []
        for event in prepared:
            event_id = event.event_id
            assert event_id is not None
            document = event.model_dump(mode="python", exclude={"event_id"})
            document["_id"] = ObjectId(event_id)
            documents.append(document)
        return documents
