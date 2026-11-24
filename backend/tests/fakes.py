from copy import deepcopy
from typing import Any

from bson import ObjectId


def _matches(document: dict[str, Any], query: dict[str, Any]) -> bool:
    for key, expected in query.items():
        value = document.get(key)
        if isinstance(expected, dict) and "$in" in expected:
            if value not in expected["$in"]:
                return False
        elif isinstance(expected, dict) and "$setOnInsert" in expected:
            return False
        elif value != expected:
            return False
    return True


class FakeResult:
    def __init__(self, *, inserted_id: ObjectId | None = None, matched_count: int = 0, upserted_id: ObjectId | None = None) -> None:
        self.inserted_id = inserted_id
        self.matched_count = matched_count
        self.upserted_id = upserted_id


class FakeCursor:
    def __init__(self, documents: list[dict[str, Any]]) -> None:
        self.documents = documents

    def sort(self, spec: Any) -> "FakeCursor":
        fields = [(spec, 1)] if isinstance(spec, str) else ([(spec, 1)] if isinstance(spec, tuple) else spec)
        for key, direction in reversed(fields):
            self.documents.sort(
                key=lambda doc: (doc.get(key) is not None, doc.get(key) if doc.get(key) is not None else ""),
                reverse=direction < 0,
            )
        return self

    def skip(self, count: int) -> "FakeCursor":
        self.documents = self.documents[count:]
        return self

    def limit(self, count: int) -> "FakeCursor":
        self.documents = self.documents[:count]
        return self

    async def to_list(self, length: int | None = None) -> list[dict[str, Any]]:
        return deepcopy(self.documents[:length]) if length is not None else deepcopy(self.documents)


class FakeCollection:
    def __init__(self) -> None:
        self.documents: list[dict[str, Any]] = []
        self.indexes: list[list[tuple[str, int]]] = []

    async def create_index(self, fields: list[tuple[str, int]]) -> str:
        self.indexes.append(fields)
        return "_".join(f"{field}_{direction}" for field, direction in fields)

    async def insert_one(self, document: dict[str, Any]) -> FakeResult:
        stored = deepcopy(document)
        stored.setdefault("_id", ObjectId())
        self.documents.append(stored)
        return FakeResult(inserted_id=stored["_id"])

    async def find_one(self, query: dict[str, Any], projection: dict[str, int] | None = None) -> dict[str, Any] | None:
        for document in self.documents:
            if _matches(document, query):
                result = deepcopy(document)
                if projection and projection.get("_id") == 1 and len(projection) == 1:
                    return {"_id": result["_id"]}
                return result
        return None

    def find(self, query: dict[str, Any]) -> FakeCursor:
        return FakeCursor([deepcopy(doc) for doc in self.documents if _matches(doc, query)])

    async def update_one(self, query: dict[str, Any], update: dict[str, Any], upsert: bool = False) -> FakeResult:
        for document in self.documents:
            if _matches(document, query):
                for key, value in deepcopy(update.get("$set", {})).items():
                    target = document
                    path = key.split(".")
                    for part in path[:-1]:
                        target = target.setdefault(part, {})
                    target[path[-1]] = value
                return FakeResult(matched_count=1)
        if upsert:
            inserted = deepcopy(update.get("$setOnInsert", {}))
            inserted.update({key: value for key, value in query.items() if not isinstance(value, dict)})
            inserted.setdefault("_id", ObjectId())
            self.documents.append(inserted)
            return FakeResult(upserted_id=inserted["_id"])
        return FakeResult()

    async def delete_one(self, query: dict[str, Any]) -> FakeResult:
        for index, document in enumerate(self.documents):
            if _matches(document, query):
                self.documents.pop(index)
                return FakeResult(matched_count=1)
        return FakeResult()

    async def count_documents(self, query: dict[str, Any]) -> int:
        return sum(_matches(document, query) for document in self.documents)


class FakeDatabase:
    def __init__(self) -> None:
        self.collections: dict[str, FakeCollection] = {}

    def __getitem__(self, name: str) -> FakeCollection:
        return self.collections.setdefault(name, FakeCollection())

    def __getattr__(self, name: str) -> FakeCollection:
        if name.startswith("__"):
            raise AttributeError(name)
        return self[name]


class FakeDatabaseManager:
    def __init__(self, *, connected: bool = True) -> None:
        self.database = FakeDatabase()
        self.client = object()
        self._connected = connected
        self.closed = False

    async def connect(self) -> None:
        return None

    async def check(self) -> bool:
        return self._connected

    async def close(self) -> None:
        self.closed = True
