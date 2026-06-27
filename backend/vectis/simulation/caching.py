"""Memoization of Monte Carlo runs — don't re-simulate identical requests.

A burst of identical observations (a sensor re-reporting the same value, a UI
refresh) shouldn't trigger a fresh 1M-scenario run each time. :class:`SimulationCache`
is a small **TTL + LRU** store keyed by a hash of ``(WorldState, ScenarioSet,
SimulationConfig)``; :class:`MemoizingMonteCarloEngine` wraps *any* engine so the
caching is orthogonal to the math (decorator, not a fork of the engine).

Design notes:
- **Key excludes volatile fields** (``WorldState.estimated_at``) so two states that
  are *semantically* identical hash the same — otherwise the timestamp would defeat
  every cache hit.
- **TTL** (seconds) bounds staleness: "the same state within seconds" hits; later it
  recomputes. **LRU** bounds memory. Pure stdlib (``hashlib`` + ``OrderedDict``).
- Caching a non-deterministic config (``seed=None``) returns the first run's draws
  for the TTL window — intended (that's the point of "don't recompute"); set a seed
  for reproducible memoization.
"""

from __future__ import annotations

import hashlib
import time
from collections import OrderedDict

from vectis.simulation.engine.monte_carlo import MonteCarloEngine
from vectis.simulation.schemas import (
    ScenarioSet,
    SimulationConfig,
    SimulationRun,
    WorldState,
)


def run_key(state: WorldState, scenarios: ScenarioSet, config: SimulationConfig) -> str:
    """Stable hash of the *semantic* run inputs (ignores volatile timestamps)."""
    blob = "\x1f".join(
        (
            state.model_dump_json(exclude={"estimated_at"}),
            scenarios.model_dump_json(),
            config.model_dump_json(),
        )
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


class SimulationCache:
    """TTL + LRU cache of :class:`SimulationRun` results, keyed by run inputs."""

    def __init__(self, *, maxsize: int = 128, ttl_seconds: float = 5.0) -> None:
        if maxsize < 1:
            raise ValueError("maxsize must be >= 1")
        self._maxsize = maxsize
        self._ttl = ttl_seconds
        self._store: OrderedDict[str, tuple[float, SimulationRun]] = OrderedDict()
        self.hits = 0
        self.misses = 0

    def get(self, key: str, *, now: float | None = None) -> SimulationRun | None:
        """Return the cached run for ``key`` if present and unexpired, else ``None``."""
        now = time.monotonic() if now is None else now
        entry = self._store.get(key)
        if entry is None:
            self.misses += 1
            return None
        stored_at, run = entry
        if now - stored_at > self._ttl:
            del self._store[key]  # expired
            self.misses += 1
            return None
        self._store.move_to_end(key)  # LRU touch
        self.hits += 1
        return run

    def put(self, key: str, run: SimulationRun, *, now: float | None = None) -> None:
        now = time.monotonic() if now is None else now
        self._store[key] = (now, run)
        self._store.move_to_end(key)
        while len(self._store) > self._maxsize:
            self._store.popitem(last=False)  # evict least-recently-used

    def clear(self) -> None:
        self._store.clear()
        self.hits = self.misses = 0

    def __len__(self) -> int:
        return len(self._store)


class MemoizingMonteCarloEngine(MonteCarloEngine):
    """Wrap a :class:`MonteCarloEngine` so identical runs are served from cache."""

    name = "memoizing_monte_carlo"

    def __init__(
        self, engine: MonteCarloEngine, cache: SimulationCache | None = None
    ) -> None:
        self._engine = engine
        self.cache = cache or SimulationCache()

    @property
    def hazard(self):  # type: ignore[no-untyped-def]  # delegate, for parity with the wrapped engine
        return getattr(self._engine, "hazard", None)

    def run(
        self, state: WorldState, scenarios: ScenarioSet, config: SimulationConfig
    ) -> SimulationRun:
        key = run_key(state, scenarios, config)
        cached = self.cache.get(key)
        if cached is not None:
            return cached
        run = self._engine.run(state, scenarios, config)
        self.cache.put(key, run)
        return run
