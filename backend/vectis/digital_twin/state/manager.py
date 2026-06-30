"""In-memory registry of active digital twins.

The :class:`StateManager` is a thin, thread-safe dictionary of ``twin_id ->
DigitalTwin``. It is the lookup the streaming layer uses to route an incoming
observation to the right twin (e.g. a California weather alert → the California twin).

Deliberately a memory store, not a DB (per the Session-10 brief). The interface —
``register`` / ``get`` / ``all`` / ``count`` — is what a future Redis- or
DB-backed store must satisfy, so swapping persistence in later means
reimplementing this one class, not its callers.

ponytail: a plain dict guarded by one lock. Fine for tens of thousands of twins in
one process; shard or move to Redis when twins must be shared across processes.
"""

from __future__ import annotations

import threading

from vectis.digital_twin.entities.base import DigitalTwin


class StateManager:
    """Thread-safe registry of live twins keyed by ``twin_id``."""

    def __init__(self) -> None:
        self._twins: dict[str, DigitalTwin] = {}
        self._lock = threading.Lock()

    def register(self, twin: DigitalTwin) -> DigitalTwin:
        """Add (or replace) a twin; returns it for convenient chaining."""
        with self._lock:
            self._twins[twin.twin_id] = twin
        return twin

    def get(self, twin_id: str) -> DigitalTwin | None:
        """Look up a twin by id (``None`` if absent). Dict reads are atomic."""
        return self._twins.get(twin_id)

    def deregister(self, twin_id: str) -> None:
        """Remove a twin if present (idempotent)."""
        with self._lock:
            self._twins.pop(twin_id, None)

    def all(self) -> list[DigitalTwin]:
        """Snapshot of all registered twins."""
        return list(self._twins.values())

    @property
    def count(self) -> int:
        return len(self._twins)
