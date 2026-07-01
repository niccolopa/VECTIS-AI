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
from abc import ABC, abstractmethod
from collections import deque
from typing import Generic, Protocol, TypeVar

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
    def model_validate_json(cls, data: str | bytes) -> _CellState: ...


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
