"""FastAPI dependencies.

The :class:`AnalysisService` is constructed once at startup and stashed on
``app.state``; these helpers expose it (and settings) to routers via DI, which
keeps handlers thin and tests easy to wire with overrides.
"""

from __future__ import annotations

from fastapi import Request

from vectis.core.config import Settings, get_settings
from vectis.services.analysis_service import AnalysisService
from vectis.streaming.broadcaster import ConnectionManager
from vectis.streaming.updater import RealTimeUpdater


def get_service(request: Request) -> AnalysisService:
    return request.app.state.service


def get_updater(request: Request) -> RealTimeUpdater:
    return request.app.state.updater


def get_broadcaster(request: Request) -> ConnectionManager:
    return request.app.state.broadcaster


def settings_dep() -> Settings:
    return get_settings()
