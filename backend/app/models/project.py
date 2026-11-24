from datetime import datetime
from typing import TypedDict

from bson import ObjectId


class ProjectDocument(TypedDict):
    _id: ObjectId
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime
