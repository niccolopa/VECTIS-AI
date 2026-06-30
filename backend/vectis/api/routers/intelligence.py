"""Decision-intelligence API — trigger the Simulation Analysis Board manually.

``POST /api/v1/intelligence/reports`` takes a region, reads that region's Digital
Twin current :class:`RiskState`, runs the LLM analysis board, and returns a
structured :class:`DecisionIntelligenceReport`. This is deliberately independent of
the real-time stream — a report can be generated on demand, not only on ingest.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from vectis.agents.board.schemas import DecisionIntelligenceReport
from vectis.agents.board.service import SimulationBoardService
from vectis.api.deps import get_updater
from vectis.digital_twin.entities.region import RegionTwin

router = APIRouter(prefix="/api/v1/intelligence", tags=["intelligence"])


class ReportRequest(BaseModel):
    region: str = "california"


@router.post("/reports")
def generate_report(body: ReportRequest, request: Request) -> DecisionIntelligenceReport:
    """Run the analysis board over a region twin's current risk state."""
    twin = get_updater(request).manager.get(body.region)
    if not isinstance(twin, RegionTwin):
        raise HTTPException(status_code=404, detail=f"No twin registered for '{body.region}'.")
    return SimulationBoardService().analyze_twin(twin)
