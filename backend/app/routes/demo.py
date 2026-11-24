from typing import Any

from fastapi import APIRouter, Depends, status

from app.core.database import get_database
from app.schemas.demo import DemoRunRequest, DemoRunResponse
from app.services.demo_service import DemoRunService

router = APIRouter(prefix="/demo", tags=["demo"])


@router.post("/run", response_model=DemoRunResponse, status_code=status.HTTP_201_CREATED)
async def execute_demo_run(payload: DemoRunRequest, database: Any = Depends(get_database)) -> dict[str, Any]:
    return await DemoRunService(database).execute(payload)
