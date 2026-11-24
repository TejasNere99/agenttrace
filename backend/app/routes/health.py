from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    application: str
    api_status: str
    database_status: str


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse | JSONResponse:
    manager = request.app.state.database_manager
    connected = await manager.check()
    response = HealthResponse(
        application="AgentTrace API",
        api_status="ok",
        database_status="connected" if connected else ("not_configured" if manager.client is None else "unavailable"),
    )
    return response if connected else JSONResponse(status_code=503, content=response.model_dump())
