"""Dashboard API — the endpoints the V2 frontend consumes.

Thin transport over :class:`~vectis.services.dashboard_service.DashboardService`
(which composes twin · engine · S13 cache · LLM board). Two operations:

- ``GET  /api/v1/dashboard/twins``           — list available twin ids.
- ``GET  /api/v1/dashboard/twins/{twin_id}`` — current state + RiskState +
  per-scenario distributions + the latest AI DecisionIntelligenceReport.
- ``POST /api/v1/dashboard/simulate/what-if`` — recompute risk for a user-modified
  state (manual sliders), synchronous, served from the cache when unchanged.

Live updates use the existing S9 ``WS /api/v1/stream/ws`` push — no new socket here.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from vectis.api.deps import get_dashboard
from vectis.services.dashboard_service import (
    TwinDashboardView,
    WhatIfRequest,
    WhatIfResult,
)

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


@router.get("/twins")
def list_twins(request: Request) -> list[str]:
    """Ids of every region twin the dashboard can display."""
    return get_dashboard(request).list_twins()


@router.get("/twins/{twin_id}")
def twin_view(twin_id: str, request: Request) -> TwinDashboardView:
    """Full dashboard payload for one twin (state, risk, branches, AI report)."""
    view = get_dashboard(request).twin_view(twin_id)
    if view is None:
        raise HTTPException(status_code=404, detail=f"No twin registered for '{twin_id}'.")
    return view


@router.post("/simulate/what-if")
def simulate_what_if(payload: WhatIfRequest, request: Request) -> WhatIfResult:
    """Run a manual What-If: recompute the Monte Carlo RiskState for a modified state."""
    result = get_dashboard(request).what_if(payload)
    if result is None:
        raise HTTPException(status_code=404, detail=f"No twin registered for '{payload.twin_id}'.")
    return result
