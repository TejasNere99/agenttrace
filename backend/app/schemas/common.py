from datetime import datetime, timezone
from typing import Annotated, Any

from bson import ObjectId
from pydantic import BaseModel, BeforeValidator, ConfigDict


def validate_object_id(value: Any) -> str:
    if isinstance(value, ObjectId):
        return str(value)
    if not isinstance(value, str) or not ObjectId.is_valid(value):
        raise ValueError("Must be a valid MongoDB ObjectId")
    return str(ObjectId(value))


def normalize_utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Datetime must include a UTC offset")
    return value.astimezone(timezone.utc)


ObjectIdString = Annotated[str, BeforeValidator(validate_object_id)]
JsonObject = dict[str, Any]


class ApiSchema(BaseModel):
    """Shared Pydantic settings for response schemas."""

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class ErrorDetails(ApiSchema):
    code: str
    message: str


class ErrorResponse(ApiSchema):
    error: ErrorDetails
