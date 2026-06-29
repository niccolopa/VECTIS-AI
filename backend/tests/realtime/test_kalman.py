"""Session 20 — Kalman filter foundation: pure math + updater convergence."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from vectis.realtime.events.base import GlobalObservation
from vectis.realtime.forecasting.kalman import (
    Gaussian,
    KalmanCellState,
    KalmanStateUpdater,
    confidence_to_variance,
    correct,
    kalman_gain,
    predict,
)
from vectis.realtime.state.store import MemoryStateStore

CELL = "44.4,8.9"
T0 = datetime(2026, 6, 29, 12, 0, 0, tzinfo=UTC)


def _obs(value: float, *, std: float | None = None, at: datetime = T0, variable: str = "temperature") -> GlobalObservation:
    return GlobalObservation(
        cell_id=CELL, variable=variable, value=value, std=std, observed_at=at, source="weather_api"
    )


# --- pure math -------------------------------------------------------------------------


def test_predict_grows_variance_keeps_mean() -> None:
    out = predict(Gaussian(30.0, 4.0), process_variance=2.0)
    assert out.mean == 30.0
    assert out.variance == 6.0


def test_high_variance_prediction_low_variance_observation_trusts_observation() -> None:
    # Uncertain prediction (var 4) + confident observation (var 1) → pull toward the obs.
    out = correct(Gaussian(30.0, 4.0), measurement=32.0, measurement_variance=1.0)
    assert abs(out.mean - 31.6) < 1e-9  # K = 0.8, heavily weighted to the observation
    assert abs(out.variance - 0.8) < 1e-9  # and more certain than either input


def test_confident_prediction_noisy_observation_barely_moves() -> None:
    out = correct(Gaussian(30.0, 0.1), measurement=50.0, measurement_variance=100.0)
    assert abs(out.mean - 30.0) < 0.05  # noisy obs almost ignored
    assert out.variance < 0.1


def test_gain_bounds() -> None:
    assert kalman_gain(0.0, 1.0) == 0.0  # certain prediction → ignore obs
    assert kalman_gain(1.0, 0.0) == 1.0  # certain obs → adopt it
    assert kalman_gain(0.0, 0.0) == 0.0  # nothing to learn


def test_confidence_to_variance_monotonic() -> None:
    assert confidence_to_variance(1.0) == 1.0
    assert confidence_to_variance(0.5) == 2.0  # less trust → more variance
    assert confidence_to_variance(0.0) == float("inf")


# --- updater integration ---------------------------------------------------------------


def test_first_observation_initializes_belief_and_version() -> None:
    updater = KalmanStateUpdater(MemoryStateStore[KalmanCellState]())
    state = updater.apply_observation(_obs(30.0, std=1.0))
    assert state.version == 1
    est = state.estimates["temperature"]
    assert est.mean == 30.0 and est.variance == 1.0
    assert "weather_api" in state.sources


def test_noisy_observations_of_stable_value_converge_and_variance_drops() -> None:
    store = MemoryStateStore[KalmanCellState]()
    updater = KalmanStateUpdater(store)

    # A stable true value of 25.0, observed with alternating noise.
    noisy = [24.0, 26.0, 24.5, 25.5, 24.8, 25.2, 25.0, 24.9, 25.1, 25.0]
    state = None
    last_variance = float("inf")
    for i, value in enumerate(noisy):
        state = updater.apply_observation(_obs(value, std=1.0, at=T0 + timedelta(seconds=i)))
        variance = state.estimates["temperature"].variance
        assert variance < last_variance  # confidence strictly increases with each reading
        last_variance = variance

    assert state is not None
    assert state.version == len(noisy)
    assert abs(state.estimates["temperature"].mean - 25.0) < 0.3  # converged near the truth
    assert state.estimates["temperature"].variance < 0.2  # and is now confident


def test_variable_names_are_canonicalized() -> None:
    store = MemoryStateStore[KalmanCellState]()
    updater = KalmanStateUpdater(store)
    updater.apply_observation(_obs(30.0, std=1.0, variable="temp"))
    state = updater.apply_observation(
        _obs(32.0, std=1.0, at=T0 + timedelta(seconds=1), variable="temp_anomaly_c")
    )
    # Both aliases fold into the one canonical "temperature" belief, not two estimates.
    assert list(state.estimates) == ["temperature"]
    assert state.version == 2


def test_history_preserves_prior_versions() -> None:
    store = MemoryStateStore[KalmanCellState]()
    updater = KalmanStateUpdater(store)
    for i, value in enumerate((10.0, 20.0, 30.0)):
        updater.apply_observation(_obs(value, std=0.5, at=T0 + timedelta(seconds=i)))

    history = store.get_history(CELL)
    assert [h.version for h in history] == [2, 1]  # newest-first superseded versions
