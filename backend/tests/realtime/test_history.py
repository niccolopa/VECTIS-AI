"""Session 39 — durable cell history under the hot tier.

Snapshot granularity under test: one row per T1 forecast, one per T2 board report —
never per screening update. Auditability, not accuracy (coefficients illustrative).
"""

from __future__ import annotations

import h3
from sqlalchemy import select

from vectis.agents.board.service import SimulationBoardService
from vectis.database.models import CellSnapshot
from vectis.database.session import get_sessionmaker, init_db
from vectis.realtime.attention import AttentionRegistry
from vectis.realtime.compute import CellForecastRunner, SharedComputeLoop
from vectis.realtime.history import HistoryRecorder
from vectis.realtime.ingestion.manager import IngestionManager
from vectis.realtime.live_stream import GlobalIngestionBroadcaster
from vectis.realtime.state.models import WorldCellState
from vectis.realtime.state.store import MemoryStateStore
from vectis.simulation.schemas import SimulationConfig

WET = h3.latlng_to_cell(22.5, 90.0, 5)
_FAST = SimulationConfig(n_iterations=1200, seed=39, parallel=False, n_workers=1)


def _snapshots(cell_id: str) -> list[CellSnapshot]:
    with get_sessionmaker()() as session:
        return list(
            session.scalars(
                select(CellSnapshot).where(CellSnapshot.cell_id == cell_id).order_by(CellSnapshot.id)
            )
        )


def _wipe(cell_id: str) -> None:
    with get_sessionmaker()() as session:
        for row in session.scalars(select(CellSnapshot).where(CellSnapshot.cell_id == cell_id)):
            session.delete(row)
        session.commit()


def test_t1_forecast_and_t2_report_each_persist_one_snapshot() -> None:
    init_db()
    _wipe(WET)
    store: MemoryStateStore[WorldCellState] = MemoryStateStore()
    store.save_state(WorldCellState(cell_id=WET, precipitation_mm=90.0, flood_alert_level=3.0))
    attention = AttentionRegistry()
    attention.set_watchlist("operator", {WET})
    recorder = HistoryRecorder()
    loop = SharedComputeLoop(
        store=store,
        attention=attention,
        ingestion=GlobalIngestionBroadcaster(store, manager=IngestionManager([])),
        runner=CellForecastRunner(config=_FAST),
        board=SimulationBoardService(),
        history=recorder,
    )
    loop.run_cycle()

    rows = _snapshots(WET)
    assert [r.trigger for r in rows] == ["t1_forecast", "board_report"]
    assert recorder.written == 2 and recorder.failed == 0

    t1, t2 = rows
    assert t1.tier == "T1" and t1.report_id is None
    assert t2.tier == "T2" and t2.report_id, "the board report row carries its report id"
    assert t1.hazard == "flood"
    assert 0.0 <= t1.risk_score <= 100.0 and 0.0 <= t1.confidence <= 1.0
    assert abs(sum(t1.posterior.values()) - 1.0) < 1e-9, "the belief entry round-trips"
    assert t1.screening.get("flood", 0.0) > 0.0
    assert t1.state and t1.state["cell_id"] == WET
    lat, lon = h3.cell_to_latlng(WET)
    assert abs(t1.lat - lat) < 1e-9 and abs(t1.lon - lon) < 1e-9


def test_screening_only_cells_write_no_history() -> None:
    init_db()
    quiet = h3.latlng_to_cell(48.0, 11.0, 5)
    _wipe(quiet)
    store: MemoryStateStore[WorldCellState] = MemoryStateStore()
    store.save_state(WorldCellState(cell_id=quiet, precipitation_mm=3.0))
    recorder = HistoryRecorder()
    loop = SharedComputeLoop(
        store=store,
        attention=AttentionRegistry(),
        ingestion=GlobalIngestionBroadcaster(store, manager=IngestionManager([])),
        runner=CellForecastRunner(config=_FAST),
        history=recorder,
    )
    for _ in range(3):
        loop.run_cycle()

    assert recorder.written == 0, "T0 screening is deliberately not persisted"
    assert _snapshots(quiet) == []
