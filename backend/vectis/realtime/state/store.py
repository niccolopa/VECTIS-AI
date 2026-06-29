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

import threading
from abc import ABC, abstractmethod
from collections import deque

from vectis.realtime.events.base import CellId
from vectis.realtime.state.models import WorldCellState

#: How many superseded versions to retain per cell in the in-memory backend.
DEFAULT_HISTORY_LIMIT = 100


class StateStore(ABC):
    """Persistence boundary for per-cell world state + its version history."""

    @abstractmethod
    def get_state(self, cell_id: CellId) -> WorldCellState | None:
        """Return the cell's current (latest) state, or ``None`` if never seen."""
        raise NotImplementedError

    @abstractmethod
    def save_state(self, cell_state: WorldCellState) -> None:
        """Persist ``cell_state`` as the new latest, retaining the prior version in history."""
        raise NotImplementedError

    @abstractmethod
    def get_history(self, cell_id: CellId, limit: int = 10) -> list[WorldCellState]:
        """Return up to ``limit`` prior versions of the cell, **newest first**."""
        raise NotImplementedError


class MemoryStateStore(StateStore):
    """In-memory store: latest state per cell + a bounded append-only history.

    Thread-safe (a single lock guards the dicts) so it can sit behind the streaming
    consumer. History is a per-cell ``deque(maxlen=history_limit)`` — superseded
    versions age out oldest-first, bounding memory while keeping recent look-back.

    # ponytail: single global lock — fine for one node. Shard by cell or move to
    # Redis/Postgres when many cells update concurrently.
    """

    def __init__(self, *, history_limit: int = DEFAULT_HISTORY_LIMIT) -> None:
        self._history_limit = history_limit
        self._latest: dict[CellId, WorldCellState] = {}
        self._history: dict[CellId, deque[WorldCellState]] = {}
        self._lock = threading.Lock()

    def get_state(self, cell_id: CellId) -> WorldCellState | None:
        with self._lock:
            return self._latest.get(cell_id)

    def save_state(self, cell_state: WorldCellState) -> None:
        with self._lock:
            prior = self._latest.get(cell_state.cell_id)
            if prior is not None:
                hist = self._history.setdefault(
                    cell_state.cell_id, deque(maxlen=self._history_limit)
                )
                hist.append(prior)
            self._latest[cell_state.cell_id] = cell_state

    def get_history(self, cell_id: CellId, limit: int = 10) -> list[WorldCellState]:
        with self._lock:
            hist = self._history.get(cell_id)
            if not hist:
                return []
            # deque is oldest→newest; reverse for newest-first, then cap at limit.
            return list(reversed(hist))[:limit]


# ponytail: RedisStateStore / PostgresStateStore go here — same three methods over a
# durable tier (Redis hash for latest + a capped stream for history; or a versioned
# `cell_states` table). The StateUpdater depends only on StateStore, so it's a drop-in.
