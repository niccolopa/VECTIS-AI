"""Tests for the V2 vectorized Monte Carlo engine.

Covers the three contracts the engine promises: **reproducibility** (same seed ⇒
same draws), **performance** (100k samples vectorized, well under 2 s), and
**correct distribution sampling** (bounds/shape). Plus parallel/serial equivalence
and the scenario-prior invariant.
"""

from __future__ import annotations

import time

import numpy as np
import pytest

from vectis.simulation.engine.distributions import (
    Constant,
    Normal,
    Poisson,
    Uniform,
    distribution_for,
)
from vectis.simulation.engine.runner import VectorizedMonteCarloEngine
from vectis.simulation.scenarios.generator import (
    WildfireScenarioGenerator,
    california_wildfire_state,
)
from vectis.simulation.schemas import (
    DistributionFamily,
    Scenario,
    ScenarioSet,
    SimulationConfig,
    StateVariable,
)


@pytest.fixture
def engine() -> VectorizedMonteCarloEngine:
    return VectorizedMonteCarloEngine()


@pytest.fixture
def state():
    return california_wildfire_state()


@pytest.fixture
def scenarios(state):
    return WildfireScenarioGenerator().generate(state)


# ── Reproducibility ──────────────────────────────────────────────────────────
def test_same_seed_yields_identical_draws(engine, state, scenarios):
    a = engine.run(state, scenarios, SimulationConfig(n_iterations=10_000, seed=42, retain_samples=True))
    b = engine.run(state, scenarios, SimulationConfig(n_iterations=10_000, seed=42, retain_samples=True))
    for oa, ob in zip(a.outcomes, b.outcomes, strict=True):
        assert oa.risk.samples == ob.risk.samples


def test_different_seed_changes_draws(engine, state, scenarios):
    a = engine.run(state, scenarios, SimulationConfig(n_iterations=10_000, seed=1, retain_samples=True))
    b = engine.run(state, scenarios, SimulationConfig(n_iterations=10_000, seed=2, retain_samples=True))
    assert a.outcomes[0].risk.samples != b.outcomes[0].risk.samples


# ── Performance / vectorization ──────────────────────────────────────────────
def test_100k_scenarios_under_two_seconds(engine, state, scenarios):
    cfg = SimulationConfig(n_iterations=100_000, seed=7)
    start = time.perf_counter()
    run = engine.run(state, scenarios, cfg)
    elapsed = time.perf_counter() - start
    assert elapsed < 2.0, f"100k×{len(scenarios.scenarios)} took {elapsed:.3f}s (budget 2s)"
    for outcome in run.outcomes:
        assert 0.0 <= outcome.risk.mean <= 100.0
        assert outcome.risk.p05 <= outcome.risk.p50 <= outcome.risk.p95
        for p in outcome.risk.exceedance.values():
            assert 0.0 <= p <= 1.0


def test_retained_samples_have_full_size_and_expected_ordering(engine, state, scenarios):
    run = engine.run(
        state, scenarios, SimulationConfig(n_iterations=100_000, seed=7, retain_samples=True)
    )
    by_id = {o.scenario_id: o for o in run.outcomes}
    assert len(by_id["baseline"].risk.samples) == 100_000
    # A hotter, drier future must not be less risky than the baseline.
    assert by_id["hotter_drier"].risk.mean > by_id["baseline"].risk.mean


# ── Distribution sampling bounds/shape ───────────────────────────────────────
def test_distribution_sampling_bounds():
    rng = np.random.default_rng(0)

    u = Uniform(2.0, 5.0).sample(rng, 5_000)
    assert u.shape == (5_000,)
    assert u.min() >= 2.0 and u.max() <= 5.0

    p = Poisson(3.0).sample(rng, 5_000)
    assert np.all(p >= 0) and np.all(p == np.floor(p))  # non-negative integers

    c = Constant(4.2).sample(rng, 16)
    assert np.allclose(c, 4.2)

    n = Normal(0.0, 1.0).sample(rng, 200_000)
    assert abs(float(n.mean())) < 0.05  # law of large numbers


def test_distribution_factory_requires_parameters():
    with pytest.raises(ValueError):
        distribution_for(StateVariable(name="t", value=1.0, family=DistributionFamily.NORMAL))


# ── Parallel execution ───────────────────────────────────────────────────────
def test_parallel_matches_serial_chunked(engine, state, scenarios):
    base = {"n_iterations": 4_000, "seed": 11, "n_workers": 4, "retain_samples": True}
    serial = engine.run(state, scenarios, SimulationConfig(parallel=False, **base))
    parallel = engine.run(state, scenarios, SimulationConfig(parallel=True, **base))
    for so, po in zip(serial.outcomes, parallel.outcomes, strict=True):
        assert so.risk.samples == po.risk.samples


# ── Scenario invariant ───────────────────────────────────────────────────────
def test_scenario_priors_must_sum_to_one():
    with pytest.raises(ValueError):
        ScenarioSet(scenarios=[Scenario(id="x", name="x", prior=0.4)])
