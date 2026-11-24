import logging
from collections.abc import Mapping
from typing import Any

from fastapi import Request
from pymongo import ASCENDING, DESCENDING, AsyncMongoClient
from pymongo.errors import PyMongoError

from app.core.config import Settings

logger = logging.getLogger("agenttrace.database")


class DatabaseManager:
    """Owns one async PyMongo client and initializes indexes idempotently."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client: AsyncMongoClient[Mapping[str, Any]] | None = None
        self.database: Any | None = None
        self.connected = False

    async def connect(self) -> None:
        if not self.settings.mongodb_uri:
            logger.info("MongoDB URI is not configured; API will start in database-unavailable mode")
            return

        try:
            self.client = AsyncMongoClient(
                self.settings.mongodb_uri,
                serverSelectionTimeoutMS=2500,
                connectTimeoutMS=2500,
                tz_aware=True,
            )
            await self.client.admin.command("ping")
            self.database = self.client[self.settings.mongodb_database]
            await self._ensure_indexes()
            self.connected = True
            logger.info("Connected to MongoDB database %s", self.settings.mongodb_database)
        except PyMongoError as exc:
            self.connected = False
            # Do not log the URI or exception text; driver messages can include topology details.
            logger.warning("MongoDB is unavailable at startup (%s)", type(exc).__name__)

    async def check(self) -> bool:
        """Ping MongoDB for a current health result rather than trusting startup state."""
        if self.client is None or self.database is None:
            self.connected = False
            return False
        try:
            await self.client.admin.command("ping")
            self.connected = True
        except PyMongoError as exc:
            self.connected = False
            logger.warning("MongoDB health check failed (%s)", type(exc).__name__)
        return self.connected

    async def close(self) -> None:
        if self.client is not None:
            await self.client.close()
        self.client = None
        self.database = None
        self.connected = False

    async def _ensure_indexes(self) -> None:
        assert self.database is not None
        indexes: dict[str, list[Any]] = {
            "projects": [[("name", ASCENDING)], [("created_at", DESCENDING)]],
            "agent_runs": [
                [("project_id", ASCENDING)],
                [("status", ASCENDING)],
                [("started_at", DESCENDING)],
                [("project_id", ASCENDING), ("started_at", DESCENDING)],
            ],
            "trace_events": [
                [("run_id", ASCENDING)],
                [("sequence_number", ASCENDING)],
                [("parent_event_id", ASCENDING)],
                [("run_id", ASCENDING), ("sequence_number", ASCENDING)],
            ],
            "evaluations": [
                [("run_id", ASCENDING)],
                [("metric_name", ASCENDING)],
                [("run_id", ASCENDING), ("metric_name", ASCENDING)],
            ],
            "experiments": [[("created_at", DESCENDING)]],
        }
        for collection_name, collection_indexes in indexes.items():
            collection = self.database[collection_name]
            for index_fields in collection_indexes:
                await collection.create_index(index_fields)


def get_database(request: Request) -> Any:
    """FastAPI dependency that exposes the single application-scoped database."""
    database = request.app.state.database_manager.database
    if database is None:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=503,
            detail={"code": "database_unavailable", "message": "MongoDB is unavailable."},
        )
    return database
