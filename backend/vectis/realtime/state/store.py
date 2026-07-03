"""State persistence — the latest cell state plus a replayable version history.

Versioning is only auditable if old versions survive. The :class:`StateStore` is the
seam that holds the **current** state per cell and an **append-only history** of the
versions it superseded, so a data scientist can ask "what was cell X five minutes ago,
before the fire started?" and get an exact snapshot back.

:class:`MemoryStateStore` is the dependency-free local/dev backend. A production
``RedisStateStore`` / ``PostgresStateStore`` implements the same three methods over a
durable tier — the rest of V3 only depends on the abstract interface.
"""

from __future__ import annotations

import os
import threading
import time
from abc import ABC, abstractmethod
from collections import OrderedDict, deque
from collections.abc import Callable
from typing import Generic, Protocol, Self, TypeVar

from vectis.core.logging import get_logger
from vectis.realtime.events.base import CellId

logger = get_logger(__name__)

#: How many superseded versions to retain per cell in the in-memory backend.
DEFAULT_HISTORY_LIMIT = 100


class _CellState(Protocol):
    """Any versioned per-cell state the store can hold — needs a ``cell_id`` and Pydantic
    JSON (de)serialization, so a durable backend can round-trip it over the wire."""

    cell_id: CellId

    def model_dump_json(self) -> str: ...

    @classmethod
    def model_validate_json(cls, data: str | bytes) -> Self: ...


#: The concrete state type a store instance holds (``WorldCellState`` for the EMA path,
#: ``KalmanCellState`` for the Session-20 filter) — so one store serves both, no fork.
StateT = TypeVar("StateT", bound=_CellState)


class StateStore(ABC, Generic[StateT]):
    """Persistence boundary for per-cell world state + its version history."""

    @abstractmethod
    def get_state(self, cell_id: CellId) -> StateT | None:
        """Return the cell's current (latest) state, or ``None`` if never seen."""
        raise NotImplementedError

    @abstractmethod
    def save_state(self, cell_state: StateT) -> None:
        """Persist ``cell_state`` as the new latest, retaining the prior version in history."""
        raise NotImplementedError

    @abstractmethod
    def get_history(self, cell_id: CellId, limit: int = 10) -> list[StateT]:
        """Return up to ``limit`` prior versions of the cell, **newest first**."""
        raise NotImplementedError

    @abstractmethod
    def active_states(self) -> list[StateT]:
        """Every currently-held cell's latest state, in one pass — the batch a screening
        sweep scores. A pure read (no recency side effect). Bounded by the *active* set when
        wrapped by :class:`EvictingStateStore`; on a bare store it is every cell held."""
        raise NotImplementedError

    @abstractmethod
    def delete(self, cell_id: CellId) -> None:
        """Drop a cell entirely (latest + history). Used by eviction; a no-op if absent."""
        raise NotImplementedError


class MemoryStateStore(StateStore[StateT], Generic[StateT]):
    """In-memory store: latest state per cell + a bounded append-only history.

    Thread-safe (a single lock guards the dicts) so it can sit behind the streaming
    consumer. History is a per-cell ``deque(maxlen=history_limit)`` — superseded
    versions age out oldest-first, bounding memory while keeping recent look-back.

    # ponytail: single global lock — fine for one node. Shard by cell or move to
    # Redis/Postgres when many cells update concurrently.
    """

    def __init__(self, *, history_limit: int = DEFAULT_HISTORY_LIMIT) -> None:
        self._history_limit = history_limit
        self._latest: dict[CellId, StateT] = {}
        self._history: dict[CellId, deque[StateT]] = {}
        self._lock = threading.Lock()

    def get_state(self, cell_id: CellId) -> StateT | None:
        with self._lock:
            return self._latest.get(cell_id)

    def save_state(self, cell_state: StateT) -> None:
        with self._lock:
            prior = self._latest.get(cell_state.cell_id)
            if prior is not None:
                hist = self._history.setdefault(
                    cell_state.cell_id, deque(maxlen=self._history_limit)
                )
                hist.append(prior)
            self._latest[cell_state.cell_id] = cell_state

    def get_history(self, cell_id: CellId, limit: int = 10) -> list[StateT]:
        with self._lock:
            hist = self._history.get(cell_id)
            if not hist:
                return []
            # deque is oldest→newest; reverse for newest-first, then cap at limit.
            return list(reversed(hist))[:limit]

    def active_cell_ids(self) -> list[CellId]:
        """The cells currently holding state — the active set to screen. No eviction here,
        so this is every cell ever written and not deleted (bound the hot set with
        :class:`EvictingStateStore` for planet-scale streams)."""
        with self._lock:
            return list(self._latest)

    def active_states(self) -> list[StateT]:
        """Every active cell's current state in one pass — the batch a screening sweep scores.
        A pure read (no recency touch), so it composes into a side-effect-free sweep."""
        with self._lock:
            return list(self._latest.values())

    def delete(self, cell_id: CellId) -> None:
        with self._lock:
            self._latest.pop(cell_id, None)
            self._history.pop(cell_id, None)


class RedisStateStore(StateStore[StateT], Generic[StateT]):
    """Durable hot tier: latest state per cell + a capped, newest-first history in Redis.

    The Session-30 promotion of the old ``ponytail:`` placeholder to a real backend, the
    exact analogue of :class:`~vectis.realtime.streams.broker.RedisStreamBroker`. Same
    three-method contract as :class:`MemoryStateStore`, so the ``StateUpdater`` drops onto
    it unchanged — only ``VECTIS_STATE_BACKEND=redis`` switches it on.

    Layout per cell: a string key holds the latest ``model_dump_json()``; a Redis list
    holds superseded versions, ``LPUSH``ed newest-first and ``LTRIM``med to ``history_limit``
    — the exact semantics of :class:`MemoryStateStore`'s ``deque(maxlen=...)``.

    Because :class:`StateStore` is a *synchronous* contract (the updaters call it inline
    inside the predict–correct step), this uses the **synchronous** ``redis`` client, not
    ``redis.asyncio``. An async store would force the whole updater/pipeline async for no
    gain — the broker is async because *its* contract is; the state store's is not.
    ``redis`` is imported lazily, so a lean install with no Redis never pays for it.

    ``model_type`` is required (unlike the in-memory store, which holds live objects): the
    store must know which concrete Pydantic model to rebuild from JSON on read.
    """

    def __init__(
        self,
        model_type: type[StateT],
        *,
        url: str = "redis://localhost:6379/0",
        history_limit: int = DEFAULT_HISTORY_LIMIT,
        key_prefix: str = "vectis:cell",
        redis_client: object | None = None,
    ) -> None:
        self._model_type = model_type
        self._url = url
        self._history_limit = history_limit
        self._prefix = key_prefix
        self._redis = redis_client

    def _client(self) -> object:
        if self._redis is None:
            try:
                import redis
            except ImportError as exc:  # pragma: no cover - exercised only without redis
                raise RuntimeError(
                    "RedisStateStore needs the 'redis' extra: pip install 'vectis[redis]'"
                ) from exc
            self._redis = redis.Redis.from_url(self._url, decode_responses=True)
        return self._redis

    def _latest_key(self, cell_id: CellId) -> str:
        return f"{self._prefix}:latest:{cell_id}"

    def _hist_key(self, cell_id: CellId) -> str:
        return f"{self._prefix}:hist:{cell_id}"

    def get_state(self, cell_id: CellId) -> StateT | None:
        raw = self._client().get(self._latest_key(cell_id))  # type: ignore[attr-defined]
        return self._model_type.model_validate_json(raw) if raw else None

    def save_state(self, cell_state: StateT) -> None:
        client = self._client()
        latest_key = self._latest_key(cell_state.cell_id)
        prior = client.get(latest_key)  # type: ignore[attr-defined]
        if prior is not None:
            hist_key = self._hist_key(cell_state.cell_id)
            client.lpush(hist_key, prior)  # type: ignore[attr-defined]  # newest-first
            client.ltrim(hist_key, 0, self._history_limit - 1)  # type: ignore[attr-defined]  # cap
        client.set(latest_key, cell_state.model_dump_json())  # type: ignore[attr-defined]

    def get_history(self, cell_id: CellId, limit: int = 10) -> list[StateT]:
        raws = self._client().lrange(self._hist_key(cell_id), 0, limit - 1)  # type: ignore[attr-defined]
        return [self._model_type.model_validate_json(r) for r in raws]

    def active_states(self) -> list[StateT]:
        client = self._client()
        pattern = f"{self._prefix}:latest:*"
        keys = list(client.scan_iter(match=pattern))  # type: ignore[attr-defined]  # bounded by hot set under eviction
        if not keys:
            return []
        raws = client.mget(keys)  # type: ignore[attr-defined]
        return [self._model_type.model_validate_json(r) for r in raws if r]

    def delete(self, cell_id: CellId) -> None:
        self._client().delete(self._latest_key(cell_id), self._hist_key(cell_id))  # type: ignore[attr-defined]


class EvictingStateStore(StateStore[StateT], Generic[StateT]):
    """TTL + LRU eviction over any :class:`StateStore` — bounds the *hot set* to the
    active cells, so memory tracks activity, never the size of the planet.

    Same design as :class:`~vectis.simulation.caching.SimulationCache` (an ``OrderedDict``
    ordered by recency + monotonic timestamps), retargeted from simulation results to cell
    state. Two bounds, both enforced on every touch:

    - **TTL** — a cell untouched for longer than ``idle_seconds`` is *dormant* and evicted.
    - **LRU** — the hot set never exceeds ``maxsize``; the least-recently-touched cell is
      evicted when a new one would overflow it.

    Eviction **drops the cell from the wrapped store** (``inner.delete``) — out of Redis
    when Redis is the backend, out of memory always.

    LIMITATION (Session 30): **there is no cold tier yet.** Eviction is a genuine delete;
    an evicted cell is gone. Its next observation rebuilds it as fresh first-touch state
    through the updater's lazy-birth path — and because nothing was persisted, that rebuilt
    cell *is* new, indistinguishable from a location never seen before. PostGIS cold-tier
    persistence + true rehydration is scheduled for Session 35; until then "rehydration"
    means "reborn from the next observation," and this is intentional, not a gap to hide.
    """

    def __init__(
        self,
        inner: StateStore[StateT],
        *,
        maxsize: int = 100_000,
        idle_seconds: float = 3600.0,
        time_fn: Callable[[], float] = time.monotonic,
        keep: Callable[[CellId], bool] | None = None,
    ) -> None:
        """``keep`` (Session 38): the attention predicate. A cell for which it returns
        True is exempt from **idle-TTL** eviction — it is re-warmed instead, so a cell
        someone is looking at (or has pinned) stays hot while watched and starts aging
        normally the moment attention moves away. The **LRU maxsize cap is still hard**:
        memory safety outranks attention, so under overflow the least-recently-touched
        unprotected cell goes first, and if literally everything is protected the LRU
        cell is evicted anyway. ``keep=None`` is exactly the pre-Session-38 behavior.
        """
        if maxsize < 1:
            raise ValueError("maxsize must be >= 1")
        self._inner = inner
        self._maxsize = maxsize
        self._idle = idle_seconds
        self._now = time_fn
        self._keep = keep
        self._touched: OrderedDict[CellId, float] = OrderedDict()  # cell → last-touch time
        self._lock = threading.Lock()
        self.evictions = 0

    @property
    def active_cells(self) -> int:
        """Cells currently in the hot set (the number the bounds keep small)."""
        return len(self._touched)

    def __len__(self) -> int:
        return len(self._touched)

    def get_state(self, cell_id: CellId) -> StateT | None:
        with self._lock:
            now = self._now()
            self._purge_expired(now)
            state = self._inner.get_state(cell_id)
            if state is not None:
                self._touch(cell_id, now)
            return state

    def save_state(self, cell_state: StateT) -> None:
        with self._lock:
            now = self._now()
            self._purge_expired(now)
            self._inner.save_state(cell_state)
            self._touch(cell_state.cell_id, now)

    def get_history(self, cell_id: CellId, limit: int = 10) -> list[StateT]:
        with self._lock:
            self._purge_expired(self._now())
            return self._inner.get_history(cell_id, limit)

    def active_cell_ids(self) -> list[CellId]:
        """The current **hot set** — exactly the cells a screening sweep should touch, never
        the whole grid. Purges dormant cells first so it reflects live activity only."""
        with self._lock:
            self._purge_expired(self._now())
            return list(self._touched)

    def active_states(self) -> list[StateT]:
        """The hot set's states in one pass, purged of dormant cells first — the batch a
        screening sweep scores. Eviction deletes from the wrapped store, so the inner store
        holds exactly the hot set; this reads it directly (no per-cell recency touch)."""
        with self._lock:
            self._purge_expired(self._now())
            return self._inner.active_states()

    def delete(self, cell_id: CellId) -> None:
        with self._lock:
            self._touched.pop(cell_id, None)
            self._inner.delete(cell_id)

    def _touch(self, cell_id: CellId, now: float) -> None:
        """Mark a cell most-recently-used; evict LRU if that overflows ``maxsize``."""
        self._touched[cell_id] = now
        self._touched.move_to_end(cell_id)
        while len(self._touched) > self._maxsize:
            self._evict_lru()

    def _evict_lru(self) -> None:
        """Evict the least-recently-touched **unprotected** cell; if every cell is
        protected, the hard memory bound wins and the LRU cell goes regardless.
        ponytail: O(n) scan when many cells are protected — fine while attention is a
        handful of viewports; index protected cells if that ever dominates."""
        victim = next(iter(self._touched))
        if self._keep is not None:
            for cell_id in self._touched:
                if not self._keep(cell_id):
                    victim = cell_id
                    break
        self._touched.pop(victim)
        self._inner.delete(victim)
        self.evictions += 1

    def _purge_expired(self, now: float) -> None:
        """Evict every cell idle longer than the TTL — unless attention protects it,
        in which case it is re-warmed (touched ``now``) instead: watched cells never
        TTL out mid-watch, and begin aging fresh the moment attention moves away."""
        while self._touched:
            cell_id, ts = next(iter(self._touched.items()))
            if now - ts <= self._idle:
                break
            if self._keep is not None and self._keep(cell_id):
                self._touched[cell_id] = now  # re-warm: attention counts as a touch
                self._touched.move_to_end(cell_id)
                continue
            self._touched.pop(cell_id)
            self._inner.delete(cell_id)
            self.evictions += 1


def get_state_store(
    model_type: type[StateT], *, history_limit: int = DEFAULT_HISTORY_LIMIT
) -> StateStore[StateT]:
    """Resolve the state-store backend from the environment (``VECTIS_STATE_BACKEND``).

    ``memory`` (default) → :class:`MemoryStateStore`; ``redis`` → :class:`RedisStateStore`
    at ``VECTIS_REDIS_URL`` (default ``redis://localhost:6379/0``). Mirrors the broker's
    :func:`~vectis.realtime.streams.broker.get_broker` env-driven selection, so switching
    memory→Redis is one env var, no code edit.
    """
    backend = os.getenv("VECTIS_STATE_BACKEND", "memory").lower()
    if backend == "redis":
        url = os.getenv("VECTIS_REDIS_URL", "redis://localhost:6379/0")
        logger.info("[INFO] using Redis state store at %s", url)
        return RedisStateStore(model_type, url=url, history_limit=history_limit)
    logger.info("[INFO] using in-memory state store (set VECTIS_STATE_BACKEND=redis for production)")
    return MemoryStateStore(history_limit=history_limit)
