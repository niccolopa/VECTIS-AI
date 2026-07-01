"""Session 19 — state estimation engine: model, store history, updater versioning."""

from __future__ import annotations

from vectis.realtime.events.base import GlobalObservation
from vectis.realtime.state.models import WorldCellState
from vectis.realtime.state.store import (
    MemoryStateStore,
    RedisStateStore,
    get_state_store,
)
from vectis.realtime.state.updater import StateUpdater


class _FakeRedis:
    """Minimal in-memory stand-in for the sync redis client (the 5 commands we use).

    Lets RedisStateStore's serialization + history-cap logic be tested with no redis
    server — the same "inject a client" seam RedisStreamBroker exposes.
    """

    def __init__(self) -> None:
        self.kv: dict[str, str] = {}
        self.lists: dict[str, list[str]] = {}

    def get(self, key: str) -> str | None:
        return self.kv.get(key)

    def set(self, key: str, value: str) -> None:
        self.kv[key] = value

    def lpush(self, key: str, *values: str) -> int:
        lst = self.lists.setdefault(key, [])
        for value in values:
            lst.insert(0, value)  # newest at head, like redis LPUSH
        return len(lst)

    def ltrim(self, key: str, start: int, end: int) -> None:
        lst = self.lists.get(key, [])
        self.lists[key] = lst[start:] if end == -1 else lst[start : end + 1]

    def lrange(self, key: str, start: int, end: int) -> list[str]:
        lst = self.lists.get(key, [])
        return lst[start:] if end == -1 else lst[start : end + 1]


def _obs(variable: str, value: float, cell: str = "44.4,8.9") -> GlobalObservation:
    return GlobalObservation(cell_id=cell, variable=variable, value=value, source="weather_api")


def test_untouched_store_holds_zero_state_objects() -> None:
    """Lazy cell birth: a store nobody has written to allocates nothing (Session 30).

    The globe is mostly dormant — memory must track *touched* cells, never the grid size.
    A cell springs into existence only on its first observation, via the updater's
    get-or-create path; until then the store is genuinely empty.
    """
    store: MemoryStateStore[WorldCellState] = MemoryStateStore()
    assert len(store._latest) == 0 and len(store._history) == 0
    assert store.get_state("cell-never-seen") is None  # a read must not materialize it
    assert len(store._latest) == 0

    # One observation → exactly one cell born, nothing pre-allocated for its neighbors.
    StateUpdater(store).apply_observation(_obs("temp_anomaly_c", 30.0, cell="only-cell"))
    assert list(store._latest) == ["only-cell"]


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


def test_redis_store_roundtrips_state_and_caps_history() -> None:
    """RedisStateStore mirrors MemoryStateStore semantics exactly (via a fake client)."""
    store: RedisStateStore[WorldCellState] = RedisStateStore(
        WorldCellState, history_limit=2, redis_client=_FakeRedis()
    )
    updater = StateUpdater(store, alpha=1.0)  # overwrite → readable values
    for value in (10.0, 20.0, 30.0, 40.0):
        updater.apply_observation(_obs("humidity_pct", value))

    latest = store.get_state("44.4,8.9")
    assert latest is not None and latest.version == 4 and latest.humidity == 40.0

    # History is newest-first and capped at history_limit (the deque(maxlen) semantics).
    history = store.get_history("44.4,8.9", limit=10)
    assert [h.humidity for h in history] == [30.0, 20.0]
    assert [h.version for h in history] == [3, 2]


def test_redis_store_unseen_cell_returns_none() -> None:
    store: RedisStateStore[WorldCellState] = RedisStateStore(
        WorldCellState, redis_client=_FakeRedis()
    )
    assert store.get_state("never-seen") is None
    assert store.get_history("never-seen") == []


def test_get_state_store_defaults_to_memory(monkeypatch) -> None:
    """No env set (lean install, no Redis) → the dependency-free in-memory backend."""
    monkeypatch.delenv("VECTIS_STATE_BACKEND", raising=False)
    store = get_state_store(WorldCellState)
    assert isinstance(store, MemoryStateStore)
