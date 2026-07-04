"""Session 39 — the belief-trajectory query API, and its restart-survival proof.

The endpoints in ``api/routers/history.py`` read the durable ``cell_snapshots`` rows
through the Session-2 database layer. The point of this file is the honest claim the
hot tier can't make: **history outlives the process**. The restart test writes rows,
disposes the engine and clears every cached session factory (``reset_engine_cache`` —
the same teardown a real restart performs), and then reads the history back through a
brand-new engine + a fresh ``TestClient``. A hit can only come from the SQLite file on
disk, never from in-memory state — that in-memory state was thrown away.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import h3
from fastapi.testclient import TestClient

from vectis.api.main import create_app
from vectis.database.models import CellSnapshot
from vectis.database.session import get_sessionmaker, init_db, reset_engine_cache

CELL = h3.latlng_to_cell(22.5, 90.0, 5)
LAT, LON = h3.cell_to_latlng(CELL)


def _write(cell_id: str, rows: list[tuple[datetime, str, float, float]]) -> None:
    """Insert ``(ts, trigger, risk, confidence)`` snapshots straight through the DB."""
    with get_sessionmaker()() as session:
        for ts, trigger, risk, conf in rows:
            session.add(
                CellSnapshot(
                    cell_id=cell_id, ts=ts, lat=LAT, lon=LON,
                    tier="T2" if trigger == "board_report" else "T1",
                    trigger=trigger, hazard="flood", risk_score=risk, confidence=conf,
                    posterior={"baseline": 1.0 - conf, "deluge": conf},
                    screening={"flood": risk}, state={"cell_id": cell_id},
                    report_id="rep1" if trigger == "board_report" else None,
                )
            )
        session.commit()


def _wipe(cell_id: str) -> None:
    from sqlalchemy import select

    with get_sessionmaker()() as session:
        for row in session.scalars(select(CellSnapshot).where(CellSnapshot.cell_id == cell_id)):
            session.delete(row)
        session.commit()


def test_cell_history_returns_the_trajectory_in_order() -> None:
    init_db()
    _wipe(CELL)
    now = datetime.now(UTC)
    _write(CELL, [
        (now - timedelta(hours=3), "t1_forecast", 40.0, 0.5),
        (now - timedelta(hours=2), "t1_forecast", 62.0, 0.6),
        (now - timedelta(hours=1), "board_report", 78.0, 0.8),
    ])
    with TestClient(create_app()) as client:
        body = client.get(f"/api/v1/history/cells/{CELL}").json()

    assert body["cell_id"] == CELL
    assert [round(p["risk"]) for p in body["points"]] == [40, 62, 78], "chronological"
    assert body["points"][-1]["tier"] == "T2"
    assert body["points"][-1]["report_id"] == "rep1"
    assert abs(sum(body["points"][0]["posterior"].values()) - 1.0) < 1e-9


def test_history_survives_a_simulated_restart() -> None:
    """Write, drop the engine + all cached sessions (a restart), read back from disk."""
    init_db()
    _wipe(CELL)
    now = datetime.now(UTC)
    _write(CELL, [
        (now - timedelta(hours=2), "t1_forecast", 55.0, 0.55),
        (now - timedelta(minutes=30), "board_report", 81.0, 0.85),
    ])

    # ── the restart: dispose the engine, forget every session factory ──────────────
    reset_engine_cache()

    # A brand-new app + engine. Nothing in memory carried over; the only source of
    # these rows is test.db on disk.
    with TestClient(create_app()) as client:
        body = client.get(f"/api/v1/history/cells/{CELL}").json()

    risks = [round(p["risk"]) for p in body["points"]]
    assert risks == [55, 81], "the trajectory survived the restart, read from the DB"
    assert body["points"][1]["report_id"] == "rep1"


def test_playback_frames_forward_fill_a_cell_across_the_window() -> None:
    """A cell analyzed once still paints in later frames — forward-filled, not flickering."""
    init_db()
    _wipe(CELL)
    now = datetime.now(UTC)
    start = now - timedelta(hours=4)
    # Falls inside step 2's slice (between cut1=-3h and cut2=-2h), so step 1 is empty.
    _write(CELL, [(now - timedelta(minutes=150), "t1_forecast", 70.0, 0.7)])

    with TestClient(create_app()) as client:
        body = client.get(
            "/api/v1/history/frames",
            params={
                "west": LON - 1, "south": LAT - 1, "east": LON + 1, "north": LAT + 1,
                "start": start.isoformat(), "end": now.isoformat(), "steps": 4,
            },
        ).json()

    # The single snapshot lands in step 2 (hour ~-2) and forward-fills steps 3 and 4.
    painted = [len(f["cells"]) for f in body["frames"]]
    assert painted == [0, 1, 1, 1], "absent before its snapshot, then held forward"
    assert body["frames"][-1]["cells"][0]["cell_id"] == CELL
