"""Tests for the V2 Bayesian update + confidence-scoring layer.

Covers the three behaviors the brief demands of an honest Bayesian loop:
1. a strong observation moves the prior in the *correct direction*,
2. multiple *consistent* observations *raise* the Confidence Score,
3. *contradictory* observations *lower* it (more uncertainty),
plus the posterior-stays-a-probability invariant, reproducibility, throughput,
and the calibration Brier metric.
"""

from __future__ import annotations

import time

import pytest

from vectis.simulation.probability.bayesian import (
    GaussianBayesianUpdater,
    Observation,
)
from vectis.simulation.probability.calibration import CalibrationRecord, brier_score
from vectis.simulation.probability.uncertainty import (
    confidence_from_entropy,
    confidence_from_variance,
    scenario_confidence,
)
from vectis.simulation.scenarios.generator import (
    WildfireScenarioGenerator,
    california_wildfire_state,
)


@pytest.fixture
def state():
    return california_wildfire_state()


@pytest.fixture
def prior(state):
    return WildfireScenarioGenerator().generate(state)


@pytest.fixture
def updater(state):
    return GaussianBayesianUpdater(state)


def _prior_of(scenario_set, scenario_id):
    return next(s.prior for s in scenario_set.scenarios if s.id == scenario_id)


# ── 1. Direction: a strong observation moves the prior correctly ─────────────
def test_strong_observation_shifts_mass_toward_matching_scenario(updater, prior):
    # +3.5 °C is well above the +2.0 °C estimate and matches "hotter_drier"
    # (baseline 2.0 + perturbation 1.5 = 3.5). Mass should move toward it.
    posterior = updater.update(prior, Observation(variable="temp_anomaly_c", value=3.5, std=0.3))

    assert _prior_of(posterior, "hotter_drier") > _prior_of(prior, "hotter_drier")
    assert _prior_of(posterior, "baseline") < _prior_of(prior, "baseline")


def test_posterior_is_a_valid_probability_distribution(updater, prior):
    posterior = updater.update(prior, Observation(variable="temp_anomaly_c", value=3.5, std=0.3))
    total = sum(s.prior for s in posterior.scenarios)
    assert abs(total - 1.0) < 1e-9  # still sums to 1 (also enforced by the schema)
    assert all(0.0 <= s.prior <= 1.0 for s in posterior.scenarios)


def test_non_discriminating_observation_leaves_prior_unchanged(updater, prior):
    # An observation no scenario predicts differently (unknown / unperturbed
    # variable) is equally likely under all branches → posterior == prior.
    posterior = updater.update(prior, Observation(variable="unknown_var", value=5.0))
    assert [s.prior for s in posterior.scenarios] == pytest.approx(
        [s.prior for s in prior.scenarios]
    )


# ── 2. Consistency raises confidence ─────────────────────────────────────────
def test_consistent_observations_increase_confidence(updater, prior):
    # Two observations that both point at "hotter_drier": a temp spike and a
    # worsened rainfall deficit (hotter_drier: -30 + -15 = -45%).
    hot = Observation(variable="temp_anomaly_c", value=3.5, std=0.3)
    dry = Observation(variable="rainfall_anomaly_pct", value=-45.0, std=4.0)

    one = updater.update(prior, hot)
    two = updater.update_batch(prior, [hot, dry])

    assert scenario_confidence(two) > scenario_confidence(one) > scenario_confidence(prior)


# ── 3. Contradiction raises uncertainty (lowers confidence) ──────────────────
def test_contradictory_observations_decrease_confidence(updater, prior):
    # One observation favors "hotter_drier", another favors "extreme_wind", with
    # deliberately matched evidential strength (each ~2.6σ from the scenarios it
    # rejects: temp Δ1.5/σ0.58, wind Δ20/σ7.8). Neither dominates, so mass splits
    # between the two branches → more spread → lower confidence than one decisive
    # observation that concentrates on a single branch.
    hot = Observation(variable="temp_anomaly_c", value=3.5, std=0.3)
    windy = Observation(variable="wind_speed_kmh", value=55.0, std=7.7)

    decisive = updater.update(prior, hot)
    conflicted = updater.update_batch(prior, [hot, windy])

    assert scenario_confidence(conflicted) < scenario_confidence(decisive)


# ── Reproducibility & throughput (quality-check claims) ──────────────────────
def test_update_is_deterministic(updater, prior):
    obs = Observation(variable="temp_anomaly_c", value=3.2, std=0.4)
    a = [s.prior for s in updater.update(prior, obs).scenarios]
    b = [s.prior for s in updater.update(prior, obs).scenarios]
    assert a == b


def test_batch_update_is_order_independent(updater, prior):
    o1 = Observation(variable="temp_anomaly_c", value=3.5, std=0.3)
    o2 = Observation(variable="rainfall_anomaly_pct", value=-45.0, std=4.0)
    a = [s.prior for s in updater.update_batch(prior, [o1, o2]).scenarios]
    b = [s.prior for s in updater.update_batch(prior, [o2, o1]).scenarios]
    assert a == pytest.approx(b)


def test_processes_1000_observations_per_second(updater, prior):
    obs = [Observation(variable="temp_anomaly_c", value=3.0, std=0.4) for _ in range(1_000)]
    start = time.perf_counter()
    updater.update_batch(prior, obs)
    elapsed = time.perf_counter() - start
    assert elapsed < 1.0, f"1000 observations took {elapsed:.3f}s (budget 1s)"


# ── Confidence-score unit behavior ───────────────────────────────────────────
def test_confidence_bounds_and_monotonicity():
    assert confidence_from_entropy([1.0, 0.0, 0.0]) == pytest.approx(1.0)  # certain
    assert confidence_from_entropy([1 / 3, 1 / 3, 1 / 3]) == pytest.approx(0.0)  # uniform
    assert confidence_from_variance(0.0, scale=1.0) == 1.0
    assert confidence_from_variance(2.0, scale=1.0) < confidence_from_variance(0.5, scale=1.0)


# ── Calibration metric ───────────────────────────────────────────────────────
def test_brier_score_rewards_accuracy():
    perfect = [CalibrationRecord(1.0, True), CalibrationRecord(0.0, False)]
    wrong = [CalibrationRecord(0.0, True), CalibrationRecord(1.0, False)]
    assert brier_score(perfect) == 0.0
    assert brier_score(wrong) == 1.0
    assert brier_score([CalibrationRecord(0.5, True), CalibrationRecord(0.5, False)]) == 0.25
