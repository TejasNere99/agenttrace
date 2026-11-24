from typing import Any

from bson import ObjectId


class PersistenceCountMismatch(RuntimeError):
    """Raised when the run's events could not all be observed after persistence."""


class EventPersistence:
    """Idempotently upserts each event by its MongoDB _id (the event ID)."""

    def __init__(self, database: Any) -> None:
        self.database = database

    async def persist(self, run_id: str, documents: list[dict[str, Any]]) -> int:
        expected_ids: set[ObjectId] = set()
        for document in documents:
            if document["run_id"] != run_id:
                raise ValueError("Cannot persist an event belonging to another run")
            if not isinstance(document.get("_id"), ObjectId):
                raise ValueError("Every persisted event must have a MongoDB ObjectId")
            if document["_id"] in expected_ids:
                raise ValueError("Cannot persist duplicate event IDs")
            expected_ids.add(document["_id"])

        collection = self.database.trace_events
        for document in documents:
            await collection.update_one(
                {"_id": document["_id"]},
                {"$setOnInsert": document},
                upsert=True,
            )

        actual_count = await collection.count_documents({"run_id": run_id})
        if actual_count < len(expected_ids):
            raise PersistenceCountMismatch("Not all trace events were persisted")
        return actual_count
