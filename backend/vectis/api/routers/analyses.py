"""Analyses resource — run an analysis and retrieve Decision Reports."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from vectis.api.deps import get_service
from vectis.core.schemas import AnalysisRequest, DecisionReport
from vectis.services.analysis_service import AnalysisService

router = APIRouter(prefix="/api/v1/analyses", tags=["analyses"])


@router.post("", response_model=DecisionReport, status_code=201)
def create_analysis(
    request: AnalysisRequest,
    service: AnalysisService = Depends(get_service),
) -> DecisionReport:
    """Run the multi-agent pipeline for a region and return the Decision Report.

    Errors for unknown regions / untrained models are mapped to 4xx by the
    domain exception handler.
    """
    return service.run(request)


@router.get("", response_model=list[dict])
def list_analyses(
    limit: int = Query(20, ge=1, le=100),
    service: AnalysisService = Depends(get_service),
) -> list[dict]:
    return service.list_recent(limit)


@router.get("/{analysis_id}", response_model=DecisionReport)
def get_analysis(
    analysis_id: str,
    service: AnalysisService = Depends(get_service),
) -> DecisionReport:
    report = service.get(analysis_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return report
