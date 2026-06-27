"""Health endpoints: liveness and readiness.

``/health`` is a cheap liveness probe (the process is up). ``/health/ready`` is a
readiness probe that verifies the database answers — used by orchestrators and
load balancers to decide whether to route traffic.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from vectis import __version__
from vectis.api.deps import settings_dep
from vectis.core.config import Settings
from vectis.database.session import ping

router = APIRouter(tags=["system"])


@router.get("/health")
def health(settings: Settings = Depends(settings_dep)) -> dict:
    """Liveness: the service is running."""
    return {
        "status": "ok",
        "version": __version__,
        "env": settings.env,
        "llm_provider": settings.llm_provider,
    }


@router.get("/health/ready")
def readiness(response: Response) -> dict:
    """Readiness: dependencies (the database) are reachable.

    Returns 200 when the database responds, 503 otherwise. The repository falls
    back to in-memory storage when the DB is down, so a not-ready result is
    informational rather than fatal for the demo path.
    """
    db_ok = ping()
    if not db_ok:
        response.status_code = 503
    return {
        "status": "ready" if db_ok else "degraded",
        "checks": {"database": "ok" if db_ok else "unavailable"},
    }
