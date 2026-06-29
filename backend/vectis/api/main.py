"""FastAPI application factory.

Wires configuration, logging, CORS, exception handling, and the analysis
service (with its repository) into an app. The service is built at startup so a
single orchestrator/model registry is reused across requests.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from vectis.core.config import get_settings
from vectis.core.exceptions import VectisError
from vectis.core.logging import configure_logging, get_logger
from vectis.database.repository import build_repository
from vectis.services.analysis_service import AnalysisService
from vectis.services.dashboard_service import DashboardService
from vectis.streaming.broadcaster import ConnectionManager
from vectis.streaming.updater import build_default_updater

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging()
    repository = build_repository()
    app.state.service = AnalysisService(repository=repository)
    app.state.updater = build_default_updater()
    # Dashboard shares the updater's twin registry, so live ingest updates show up.
    app.state.dashboard = DashboardService(app.state.updater.manager)
    app.state.broadcaster = ConnectionManager()
    log.info("api.startup", env=settings.env, llm_provider=settings.llm_provider)
    yield
    log.info("api.shutdown")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="VECTIS",
        version="1.0.0",
        summary="Autonomous Intelligence System for Decision Analysis",
        description="Explainable, human-in-the-loop decision intelligence. "
                    "First vertical: climate (wildfire) risk.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(VectisError)
    async def _vectis_error_handler(_: Request, exc: VectisError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": str(exc)}},
        )

    # Routers (imported here to avoid circulars at module import time).
    from vectis.api.routers import (
        analyses,
        dashboard,
        health,
        intelligence,
        live,
        models,
        regions,
        stream,
    )

    app.include_router(health.router)
    app.include_router(analyses.router)
    app.include_router(regions.router)
    app.include_router(models.router)
    app.include_router(stream.router)
    app.include_router(intelligence.router)
    app.include_router(dashboard.router)
    app.include_router(live.router)
    return app


app = create_app()
