"""History recording — the durable layer under the hot tier (Session 39).

The ``EvictingStateStore`` keeps the *present* fast; this module makes the *past*
survive eviction and process restarts. It reuses the Session-2 database layer (the
one engine/sessionmaker in ``database.session``) — no parallel DB access path.

**When a snapshot is written** (the documented granularity): on every T1 forecast and
every T2 board report, exactly where the shared compute loop produces them. The
tiering budgets bound the write rate structurally (≤ max_t1 + max_t2 rows per cycle),
so persistence load tracks promoted attention, not the size of the hot set. Screening
updates are deliberately not persisted — 100k near-free point estimates per cycle is
noise, not history.

Recording is best-effort: a database hiccup must degrade to "a gap in the audit
trail", never to a dead compute loop.
"""

from __future__ import annotations

from collections.abc import Callable

import h3
from sqlalchemy.orm import Session, sessionmaker

from vectis.core.logging import get_logger
from vectis.database.models import CellSnapshot
from vectis.database.session import get_sessionmaker
from vectis.realtime.pipeline import ForecastResult
from vectis.realtime.state.models import WorldCellState

logger = get_logger(__name__)


class HistoryRecorder:
    """Append cell snapshots through the shared session factory."""

    def __init__(self, session_factory: sessionmaker[Session] | None = None) -> None:
        # Resolved lazily so importing this module never touches the database.
        self._factory: Callable[[], Session] | None = session_factory
        self.written = 0
        self.failed = 0

    def _session(self) -> Session:
        if self._factory is None:
            self._factory = get_sessionmaker()
        return self._factory()

    def record_forecast(
        self,
        state: WorldCellState,
        result: ForecastResult,
        *,
        hazard: str,
        screening: dict[str, float],
        trigger: str = "t1_forecast",
    ) -> None:
        """One snapshot row for a fresh T1 forecast (or T2 report — see ``trigger``)."""
        lat, lon = h3.cell_to_latlng(state.cell_id)
        snapshot = CellSnapshot(
            cell_id=state.cell_id,
            lat=lat,
            lon=lon,
            tier="T2" if result.report is not None else "T1",
            trigger=trigger,
            hazard=hazard,
            risk_score=result.risk_score,
            confidence=result.confidence,
            posterior=dict(result.posterior),
            screening=dict(screening),
            state=state.model_dump(mode="json"),
            report_id=result.report.report_id if result.report is not None else None,
        )
        try:
            with self._session() as session:
                session.add(snapshot)
                session.commit()
            self.written += 1
        except Exception:  # a DB hiccup is an audit gap, never a dead loop
            self.failed += 1
            logger.exception("[ERROR] failed to persist snapshot for cell %s", state.cell_id)
