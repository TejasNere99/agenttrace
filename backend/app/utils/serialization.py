from typing import Any

from bson import ObjectId


def mongo_to_api(document: dict[str, Any] | None) -> dict[str, Any] | None:
    """Convert MongoDB IDs (including nested references) to JSON-safe strings."""
    if document is None:
        return None

    def convert(value: Any) -> Any:
        if isinstance(value, ObjectId):
            return str(value)
        if isinstance(value, dict):
            return {key: convert(item) for key, item in value.items()}
        if isinstance(value, list):
            return [convert(item) for item in value]
        if isinstance(value, tuple):
            return [convert(item) for item in value]
        return value

    serialized = convert(document)
    serialized["id"] = str(serialized.pop("_id"))
    return serialized
