from datetime import datetime
from typing import TypedDict

from bson import ObjectId


class ExperimentDocument(TypedDict):
    _id: ObjectId
    name: str
    description: str | None
    run_ids: list[str]
    created_at: datetime
    updated_at: datetime
