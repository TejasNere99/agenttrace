from typing import Any

from fastapi import APIRouter, Depends, Query, status

from app.core.database import get_database
from app.schemas.project import ProjectCreate, ProjectResponse, ProjectUpdate
from app.services import project_service

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(payload: ProjectCreate, database: Any = Depends(get_database)) -> dict[str, Any]:
    return await project_service.create_project(database, payload.model_dump())


@router.get("", response_model=list[ProjectResponse])
async def list_projects(
    database: Any = Depends(get_database),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[dict[str, Any]]:
    return await project_service.list_projects(database, skip=skip, limit=limit)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: str, database: Any = Depends(get_database)) -> dict[str, Any]:
    return await project_service.get_project(database, project_id)


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(project_id: str, payload: ProjectUpdate, database: Any = Depends(get_database)) -> dict[str, Any]:
    return await project_service.update_project(database, project_id, payload.model_dump(exclude_unset=True))


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(project_id: str, database: Any = Depends(get_database)) -> None:
    await project_service.delete_project(database, project_id)
