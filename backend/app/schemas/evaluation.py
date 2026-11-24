from datetime import datetime
from enum import StrEnum

from pydantic import Field

from app.schemas.common import ApiSchema, ObjectIdString


class GroundTruthStatus(StrEnum):
    available = "available"
    unavailable = "unavailable"
    unverified = "unverified"


class EvaluationResponse(ApiSchema):
    id: ObjectIdString
    run_id: ObjectIdString
    metric_name: str = Field(min_length=1, max_length=150)
    metric_value: float = Field(allow_inf_nan=False)
    ground_truth_status: GroundTruthStatus
    created_at: datetime
