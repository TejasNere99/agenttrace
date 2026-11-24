from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from app.core.database import get_database
from app.schemas.agent_run import AgentRunCreate, AgentRunResponse, RunStatus
from app.schemas.demo import RunSummary
from app.schemas.trace_event import TraceEventResponse
from app.services import run_service
from app.services.run_manager import RunManager
from app.services.trace_service import TraceRetrievalService
from app.debugging.debug_service import DebugAnalysisService
from app.utils.serialization import mongo_to_api

router = APIRouter(prefix="/runs", tags=["runs"])


@router.post("", response_model=AgentRunResponse, status_code=201)
async def create_run(payload: AgentRunCreate, database: Any = Depends(get_database)) -> dict[str, Any]:
    _run_id, document = await RunManager(database).create_run(
        project_id=payload.project_id,
        task=payload.task,
        agent_name=payload.agent_name,
    )
    return mongo_to_api(document) or {}


@router.get("", response_model=list[AgentRunResponse])
async def list_runs(
    database: Any = Depends(get_database),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    project_id: str | None = None,
    run_status: Annotated[RunStatus | None, Query(alias="status")] = None,
) -> list[dict[str, Any]]:
    return await run_service.list_runs(
        database,
        skip=skip,
        limit=limit,
        project_id=project_id,
        status=run_status.value if run_status is not None else None,
    )


@router.get("/{run_id}", response_model=AgentRunResponse)
async def get_run(run_id: str, database: Any = Depends(get_database)) -> dict[str, Any]:
    return await run_service.get_run(database, run_id)


@router.get("/{run_id}/events", response_model=list[TraceEventResponse])
async def get_run_events(
    run_id: str,
    database: Any = Depends(get_database),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=200, ge=1, le=1000),
) -> list[dict[str, Any]]:
    return await run_service.list_run_events(database, run_id, skip=skip, limit=limit)


@router.get("/{run_id}/summary", response_model=RunSummary)
async def get_run_summary(run_id: str, database: Any = Depends(get_database)) -> dict[str, Any]:
    return await TraceRetrievalService(database).get_summary(run_id)


@router.get("/{run_id}/graph")
async def get_run_graph(run_id: str, database: Any = Depends(get_database)) -> dict[str, Any]:
    return await DebugAnalysisService(database).get_graph(run_id)


@router.get("/{run_id}/debug")
async def get_run_debug_analysis(run_id: str, database: Any = Depends(get_database)) -> dict[str, Any]:
    return await DebugAnalysisService(database).get_debug_analysis(run_id)
