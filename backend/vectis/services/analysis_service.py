"""Analysis service — the seam between the API and the agent system.

Runs an analysis through the orchestrator, persists the resulting Decision
Report via the repository, and serves stored reports back. Keeping this logic
out of the routers makes it independently testable and reusable (CLI, jobs).
"""

from __future__ import annotations

from vectis.agents.orchestrator import get_orchestrator
from vectis.agents.runtime import BaseOrchestrator
from vectis.core.logging import get_logger
from vectis.core.schemas import AnalysisRequest, DecisionReport
from vectis.database.repository import AnalysisRepository

log = get_logger(__name__)


class AnalysisService:
    def __init__(self, repository: AnalysisRepository,
                 orchestrator: BaseOrchestrator | None = None) -> None:
        self.repository = repository
        # Engine selected by VECTIS_ORCHESTRATOR (custom default | langgraph).
        self.orchestrator = orchestrator or get_orchestrator()

    def run(self, request: AnalysisRequest) -> DecisionReport:
        report = self.orchestrator.run(request)
        self.repository.save(report)
        log.info("analysis.persisted", id=report.id, region=report.region,
                 risk=report.risk_score)
        return report

    def get(self, analysis_id: str) -> DecisionReport | None:
        return self.repository.get(analysis_id)

    def list_recent(self, limit: int = 20) -> list[dict]:
        return self.repository.list_recent(limit)

    def delete(self, analysis_id: str) -> bool:
        deleted = self.repository.delete(analysis_id)
        if deleted:
            log.info("analysis.deleted", id=analysis_id)
        return deleted
