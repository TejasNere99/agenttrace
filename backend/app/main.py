import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pymongo.errors import PyMongoError

from app.core.config import Settings, get_settings
from app.core.database import DatabaseManager
from app.routes import demo, health, projects, runs

logger = logging.getLogger("agenttrace.api")


def _error(code: str, message: str, *, details: list[dict[str, str]] | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"error": {"code": code, "message": message}}
    if details is not None:
        body["error"]["details"] = details
    return body


def create_app(settings: Settings | None = None, database_manager: Any | None = None) -> FastAPI:
    configured = settings or get_settings()
    manager = database_manager or DatabaseManager(configured)

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        application.state.database_manager = manager
        await manager.connect()
        try:
            yield
        finally:
            await manager.close()

    application = FastAPI(
        title="AgentTrace API",
        description="Backend foundation for projects and recorded agent run traces.",
        version="0.1.0",
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=configured.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
    )
    application.include_router(health.router, prefix="/api")
    application.include_router(projects.router, prefix="/api")
    application.include_router(runs.router, prefix="/api")
    application.include_router(demo.router, prefix="/api")

    @application.exception_handler(HTTPException)
    async def http_error_handler(_request: Request, exc: HTTPException) -> JSONResponse:
        if isinstance(exc.detail, dict) and "code" in exc.detail and "message" in exc.detail:
            code, message = exc.detail["code"], exc.detail["message"]
        else:
            code = {400: "bad_request", 404: "not_found", 409: "conflict", 503: "service_unavailable"}.get(exc.status_code, "http_error")
            message = str(exc.detail) if exc.status_code < 500 else "The requested service is unavailable."
        return JSONResponse(status_code=exc.status_code, content=_error(code, message), headers=exc.headers)

    @application.exception_handler(RequestValidationError)
    async def validation_error_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            {"field": ".".join(str(part) for part in error.get("loc", ())), "message": error["msg"], "type": error["type"]}
            for error in exc.errors()
        ]
        return JSONResponse(status_code=422, content=_error("validation_error", "Request validation failed.", details=details))

    @application.exception_handler(PyMongoError)
    async def database_error_handler(_request: Request, exc: PyMongoError) -> JSONResponse:
        logger.warning("MongoDB request failed (%s)", type(exc).__name__)
        return JSONResponse(status_code=503, content=_error("database_unavailable", "MongoDB is unavailable."))

    @application.exception_handler(Exception)
    async def unexpected_error_handler(_request: Request, exc: Exception) -> JSONResponse:
        # Keep the response and log free of exception text, which may include connection data.
        logger.error("Unhandled API error (%s)", type(exc).__name__)
        return JSONResponse(status_code=500, content=_error("internal_error", "An unexpected error occurred."))

    return application


app = create_app()
