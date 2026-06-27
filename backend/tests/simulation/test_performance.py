"""Performance / scale tests for the V2 Monte Carlo engine (Session 13).

Covers the three claims of the scale work: 1M scenarios run without blowing up,
the cache intercepts identical back-to-back runs, and parallel execution is
byte-identical to serial at the same ``(seed, n_workers)``. The heaviest runs are
marked ``slow`` (they still run by default; deselect with ``-m "not slow"``).
"""

from __future__ import annotations

import numpy as np
import pytest

from vectis.simulation.caching import (
    MemoizingMonteCarloEngine,
    SimulationCache,
    run_key,
)
from vectis.simulation.engine.distributed import LocalClusterStub, RayEngineAdapter
from vectis.simulation.engine.monte_carlo import MonteCarloEngine
from vectis.simulation.engine.runner import VectorizedMonteCarloEngine, resolve_workers
from vectis.simulation.scenarios.generator import (
    WildfireScenarioGenerator,
    liguria_wildfire_state,
)
from vectis.simulation.schemas import SimulationConfig, SimulationRun


@pytest.fixture
def state():
    return liguria_wildfire_state()


@pytest.fixture
def scenarios(state):
    return WildfireScenarioGenerator().generate(state)


# ── 1M scale ─────────────────────────────────────────────────────────────────
@pytest.mark.slow
def test_one_million_runs_execute(state, scenarios):
    engine = VectorizedMonteCarloEngine()
    run = engine.run(state, scenarios, SimulationConfig(n_iterations=1_000_000, seed=7))
    assert len(run.outcomes) == 3
    for o in run.outcomes:
        assert 0.0 <= o.risk.mean <= 100.0
        assert o.risk.p05 <= o.risk.p50 <= o.risk.p95
        assert o.risk.samples is None  # not retained ⇒ no 24MB on the wire


# ── Cache intercepts identical runs ──────────────────────────────────────────
class _CountingEngine(MonteCarloEngine):
    """Wraps the real engine and counts how often it actually computes."""

    def __init__(self) -> None:
        self._engine = VectorizedMonteCarloEngine()
        self.calls = 0

    def run(self, state, scenarios, config) -> SimulationRun:  # type: ignore[no-untyped-def]
        self.calls += 1
        return self._engine.run(state, scenarios, config)


def test_cache_intercepts_identical_back_to_back_runs(state, scenarios):
    inner = _CountingEngine()
    engine = MemoizingMonteCarloEngine(inner)
    cfg = SimulationConfig(n_iterations=5_000, seed=1)

    r1 = engine.run(state, scenarios, cfg)
    r2 = engine.run(state, scenarios, cfg)  # identical inputs ⇒ served from cache

    assert inner.calls == 1  # the engine ran exactly once
    assert r1 is r2
    assert engine.cache.hits == 1 and engine.cache.misses == 1


def test_cache_misses_when_inputs_change(state, scenarios):
    inner = _CountingEngine()
    engine = MemoizingMonteCarloEngine(inner)
    engine.run(state, scenarios, SimulationConfig(n_iterations=5_000, seed=1))
    engine.run(state, scenarios, SimulationConfig(n_iterations=5_000, seed=2))  # different seed
    assert inner.calls == 2


def test_cache_key_ignores_volatile_timestamp(scenarios):
    # Two semantically-identical states (built separately, so distinct objects and
    # possibly different estimated_at timestamps) must hash to the same run key.
    cfg = SimulationConfig(n_iterations=10, seed=1)
    s1 = liguria_wildfire_state()
    s2 = liguria_wildfire_state()
    assert s1 is not s2
    assert run_key(s1, scenarios, cfg) == run_key(s2, scenarios, cfg)


def test_cache_ttl_expires(state, scenarios):
    cache = SimulationCache(ttl_seconds=10.0)
    cfg = SimulationConfig(n_iterations=10, seed=1)
    key = run_key(state, scenarios, cfg)
    run = VectorizedMonteCarloEngine().run(state, scenarios, cfg)
    cache.put(key, run, now=100.0)
    assert cache.get(key, now=105.0) is run        # within TTL
    assert cache.get(key, now=120.0) is None       # expired


# ── Parallel == serial (byte-identical), and the distributed adapter ─────────
@pytest.mark.slow
def test_parallel_matches_serial_100k(state, scenarios):
    engine = VectorizedMonteCarloEngine()
    base = {"n_iterations": 100_000, "seed": 11, "n_workers": 4, "retain_samples": True}
    serial = engine.run(state, scenarios, SimulationConfig(parallel=False, **base))
    parallel = engine.run(state, scenarios, SimulationConfig(parallel=True, **base))
    for so, po in zip(serial.outcomes, parallel.outcomes, strict=True):
        assert np.array_equal(so.risk.samples, po.risk.samples)


def test_distributed_adapter_matches_serial(state, scenarios):
    # The Ray-style adapter (local stub) must produce identical math to the
    # serial-chunked engine for the same (seed, n_workers).
    cfg = {"n_iterations": 20_000, "seed": 5, "n_workers": 4, "retain_samples": True}
    serial = VectorizedMonteCarloEngine().run(state, scenarios, SimulationConfig(parallel=False, **cfg))
    dist = RayEngineAdapter().run(state, scenarios, SimulationConfig(**cfg))
    for so, do in zip(serial.outcomes, dist.outcomes, strict=True):
        assert so.risk.samples == do.risk.samples
    assert isinstance(RayEngineAdapter().cluster, LocalClusterStub)


def test_resolve_workers_auto():
    assert resolve_workers(4) == 4          # explicit honored
    assert resolve_workers(0) >= 1          # auto ⇒ at least 1
    assert resolve_workers(1) == 1          # default single thread
