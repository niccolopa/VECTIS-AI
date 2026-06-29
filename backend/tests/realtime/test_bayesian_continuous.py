"""Session 21 — Bayesian Continuous Update Engine: probability shift + numerical stability."""

from __future__ import annotations

import math

from vectis.realtime.forecasting.bayesian import (
    ContinuousBayesianUpdater,
    ScenarioPriors,
    ScenarioProfile,
)
from vectis.realtime.forecasting.kalman.state_model import KalmanCellState, VariableEstimate

CELL = "44.4,8.9"

PROFILES = {
    "baseline": ScenarioProfile(
        scenario_id="baseline",
        expected={"drought_index": 0.30, "wind_speed": 20.0},
        spread={"drought_index": 0.35, "wind_speed": 15.0},
    ),
    "fire": ScenarioProfile(
        scenario_id="fire",
        expected={"drought_index": 0.70, "wind_speed": 40.0},
        spread={"drought_index": 0.35, "wind_speed": 15.0},
    ),
}


def _state(*, drought: float, wind: float, var: float = 0.01) -> KalmanCellState:
    return KalmanCellState(
        cell_id=CELL,
        estimates={
            "drought_index": VariableEstimate(mean=drought, variance=var),
            "wind_speed": VariableEstimate(mean=wind, variance=var * 100),
        },
    )


def _updater(*, relax_rate: float = 0.0) -> ContinuousBayesianUpdater:
    priors = ScenarioPriors(
        {"baseline": 0.55, "fire": 0.45},
        baseline={"baseline": 0.5, "fire": 0.5},
        relax_rate=relax_rate,
    )
    return ContinuousBayesianUpdater(PROFILES, priors)


def test_drought_and_wind_shift_fire_risk_upward() -> None:
    """45% prior + severe drought / high wind → posterior fire risk ~68%."""
    updater = _updater()
    assert updater.probabilities["fire"] == 0.45

    posterior = updater.update_probabilities(_state(drought=0.65, wind=35.0))

    assert posterior["fire"] > 0.45  # belief moved toward fire
    assert 0.63 <= posterior["fire"] <= 0.73  # lands on the brief's ~68% target
    assert math.isclose(posterior["baseline"] + posterior["fire"], 1.0)


def test_thousand_updates_stay_normalized_without_nans() -> None:
    """1,000 continuous ticks: probabilities sum to 1, never NaN/inf, never exact 0/1."""
    updater = _updater(relax_rate=0.05)
    state = _state(drought=0.9, wind=55.0)  # strong, one-sided fire evidence

    for _ in range(1000):
        post = updater.update_probabilities(state)
        total = sum(post.values())
        assert math.isclose(total, 1.0, abs_tol=1e-9), total
        for p in post.values():
            assert math.isfinite(p)
            assert 0.0 < p < 1.0  # relaxation keeps the belief off the 0/100 trap


def test_no_certainty_trap_allows_recovery() -> None:
    """After saturating on fire evidence, an opposite observation can still pull it back."""
    updater = _updater(relax_rate=0.05)
    for _ in range(200):
        updater.update_probabilities(_state(drought=0.95, wind=60.0))
    assert updater.probabilities["fire"] > 0.9  # near-certain, but not locked at 1.0

    # A run of clearly-benign observations recovers the baseline belief.
    for _ in range(200):
        updater.update_probabilities(_state(drought=0.1, wind=5.0))
    assert updater.probabilities["fire"] < 0.1
