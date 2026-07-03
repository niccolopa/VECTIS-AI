"""FastAPI application factory.

Wires configuration, logging, CORS, exception handling, and the analysis
service (with its repository) into an app. The service is built at startup so a
single orchestrator/model registry is reused across requests.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from vectis.agents.board.service import SimulationBoardService
from vectis.api.routers.tiles import TileCache
from vectis.core.config import get_settings
from vectis.core.exceptions import VectisError
from vectis.core.logging import configure_logging, get_logger
from vectis.database.repository import build_repository
from vectis.realtime.attention import AttentionRegistry
from vectis.realtime.compute import SharedComputeLoop
from vectis.realtime.history import HistoryRecorder
from vectis.realtime.live_stream import (
    GlobalIngestionBroadcaster,
    LiveClimateStream,
    LiveStreamBroadcaster,
)
from vectis.realtime.state.models import WorldCellState
from vectis.realtime.state.store import EvictingStateStore, MemoryStateStore
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
    # ONE global V3 pipeline, fanned out to every SSE viewer (not one pipeline per connection).
    app.state.live_stream = LiveStreamBroadcaster(LiveClimateStream())
    # Who is looking where (Session 38): SSE handlers register viewports/watchlists;
    # eviction and the warming cadence consult it.
    app.state.attention = AttentionRegistry()
    # The active cell set the tile endpoint screens — populated by the global ingestion
    # broadcaster below, which polls the Session-31 planetary feeds into it each tick.
    # TTL+LRU bounded (Session 30), with attention-protected cells exempt from idle
    # eviction while someone is actually watching them (Session 38).
    app.state.tile_store = EvictingStateStore(
        MemoryStateStore[WorldCellState](), keep=app.state.attention.protects
    )
    app.state.tile_cache = TileCache()
    app.state.global_ingestion = GlobalIngestionBroadcaster(app.state.tile_store)
    # ONE shared tiered compute loop (Session 38): it owns the tick — polling the feeds
    # via the broadcaster, screening on the warming cadence, and running the budgeted
    # T1/T2 tiers — so SSE connections are fan-out queues, never compute loops.
    app.state.compute = SharedComputeLoop(
        store=app.state.tile_store,
        attention=app.state.attention,
        ingestion=app.state.global_ingestion,
        board=SimulationBoardService(),
        # Session 39: T1/T2 outcomes persist durably under the hot tier — the write
        # rate is structurally bounded by the tiering budgets.
        history=HistoryRecorder(),
    )
    await app.state.live_stream.start()
    # Tests set VECTIS_GLOBAL_INGESTION=0: the loop writes real global events into the
    # same tile_store their assertions seed, so it must not race them. The loop object
    # still exists — tests drive ticks deterministically via run_cycle().
    if os.getenv("VECTIS_GLOBAL_INGESTION", "1") != "0":
        await app.state.compute.start()
    log.info("api.startup", env=settings.env, llm_provider=settings.llm_provider)
    yield
    await app.state.compute.stop()
    await app.state.live_stream.stop()
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
        cells,
        dashboard,
        health,
        intelligence,
        live,
        models,
        regions,
        stream,
        tiles,
        watchlist,
    )

    app.include_router(health.router)
    app.include_router(analyses.router)
    app.include_router(regions.router)
    app.include_router(models.router)
    app.include_router(stream.router)
    app.include_router(intelligence.router)
    app.include_router(dashboard.router)
    app.include_router(live.router)
    app.include_router(tiles.router)
    app.include_router(cells.router)
    app.include_router(watchlist.router)
    return app


app = create_app()
