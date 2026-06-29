"""Session 19 — state estimation engine: model, store history, updater versioning."""

from __future__ import annotations

from vectis.realtime.events.base import GlobalObservation
from vectis.realtime.state.models import WorldCellState
from vectis.realtime.state.store import MemoryStateStore
from vectis.realtime.state.updater import StateUpdater


def _obs(variable: str, value: float, cell: str = "44.4,8.9") -> GlobalObservation:
    return GlobalObservation(cell_id=cell, variable=variable, value=value, source="weather_api")


def test_fresh_state_initializes_empty_and_unversioned() -> None:
    state = WorldCellState(cell_id="44.4,8.9")
    assert state.version == 0
    assert state.temperature is None and state.fire_risk is None
    assert state.sources == []


def test_apply_observation_updates_variable_and_increments_version() -> None:
    updater = StateUpdater(MemoryStateStore(), alpha=0.5)

    first = updater.apply_observation(_obs("temp_anomaly_c", 30.0))
    assert first.version == 1
    assert first.temperature == 30.0  # first reading sets the value directly
    assert "weather_api" in first.sources

    second = updater.apply_observation(_obs("temp_anomaly_c", 40.0))
    assert second.version == 2
    assert second.temperature == 35.0  # EMA: 0.5*40 + 0.5*30


def test_unknown_variable_is_kept_in_extra() -> None:
    updater = StateUpdater(MemoryStateStore())
    state = updater.apply_observation(_obs("soil_moisture", 0.2))
    assert state.extra["soil_moisture"] == 0.2


def test_store_retrieves_versioned_history_newest_first() -> None:
    store = MemoryStateStore()
    updater = StateUpdater(store, alpha=1.0)  # overwrite, so values are easy to read

    for value in (10.0, 20.0, 30.0):
        updater.apply_observation(_obs("humidity_pct", value))

    latest = store.get_state("44.4,8.9")
    assert latest is not None and latest.version == 3 and latest.humidity == 30.0

    # History holds the two superseded versions, newest first.
    history = store.get_history("44.4,8.9")
    assert [h.humidity for h in history] == [20.0, 10.0]
    assert [h.version for h in history] == [2, 1]


def test_history_is_bounded_by_limit() -> None:
    store = MemoryStateStore(history_limit=2)
    updater = StateUpdater(store, alpha=1.0)
    for value in (1.0, 2.0, 3.0, 4.0, 5.0):
        updater.apply_observation(_obs("drought_index", value))

    history = store.get_history("44.4,8.9", limit=10)
    assert [h.drought_index for h in history] == [4.0, 3.0]  # only the 2 most recent kept
