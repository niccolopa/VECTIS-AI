"""FastAPI dependencies.

The :class:`AnalysisService` is constructed once at startup and stashed on
``app.state``; these helpers expose it (and settings) to routers via DI, which
keeps handlers thin and tests easy to wire with overrides.
"""

from __future__ import annotations

from fastapi import Request

from vectis.core.config import Settings, get_settings
from vectis.services.analysis_service import AnalysisService


def get_service(request: Request) -> AnalysisService:
    return request.app.state.service


def settings_dep() -> Settings:
    return get_settings()
