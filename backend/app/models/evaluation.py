from datetime import datetime
from typing import Literal, TypedDict

from bson import ObjectId

GroundTruthStatusValue = Literal["available", "unavailable", "unverified"]


class EvaluationDocument(TypedDict):
    _id: ObjectId
    run_id: str
    metric_name: str
    metric_value: float
    ground_truth_status: GroundTruthStatusValue
    created_at: datetime
