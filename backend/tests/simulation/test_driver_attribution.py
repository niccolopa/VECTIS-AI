"""Session 41 — closed-form driver attribution on every HazardModel.

The whole point: each factor's contribution is the model's OWN computation, exposed —
``coefᵢ × (inputᵢ − baselineᵢ)`` in log-odds for the logistic hazards, the exact analogous
log-rate decomposition for the Omori–Poisson earthquake model. No SHAP, no approximation.
These tests pin the sign, the exactness, the ranking, and the honesty caveat.
"""

from __future__ import annotations

import math

import numpy as np

from vectis.simulation.models.base import UNCALIBRATED_DRIVER_CAVEAT
from vectis.simulation.models.cyclone import CycloneHazardModel
from vectis.simulation.models.earthquake import EarthquakeImpactModel
from vectis.simulation.models.flood import FloodHazardModel
from vectis.simulation.models.wildfire import WildfireHazardModel


def _col(x: float) -> np.ndarray:
    return np.array([x], dtype=float)


def test_logistic_contribution_is_exactly_coef_times_deviation() -> None:
    """Wildfire (base-class path): every driver equals coef × (input − baseline), exactly."""
    model = WildfireHazardModel()
    baseline = {"temp_anomaly_c": 0.0, "wind_speed_kmh": 10.0, "ignition_sources": 0.0}
    inputs = {
        "temp_anomaly_c": _col(6.0),
        "wind_speed_kmh": _col(40.0),
        "ignition_sources": _col(1.0),
    }
    drivers = {d.factor: d for d in model.explain(inputs, baseline)}
    for name, d in drivers.items():
        assert d.contribution == model.coefficients[name] * (d.input_value - d.baseline_value)
    # Hotter/windier/more ignition than baseline → each raises risk.
    assert all(d.direction == "increases" for d in drivers.values())
    # rainfall_anomaly is absent from inputs → it produces no driver (honest omission).
    assert "rainfall_anomaly_pct" not in drivers


def test_drivers_are_ranked_by_absolute_contribution() -> None:
    """Ranking is by |contribution|, largest first — the V1 report's ordering."""
    model = FloodHazardModel()
    baseline = {"precipitation_mm": 0.0, "flood_alert_level": 1.0}
    drivers = model.explain(
        {"precipitation_mm": _col(120.0), "flood_alert_level": _col(3.0)}, baseline
    )
    mags = [abs(d.contribution) for d in drivers]
    assert mags == sorted(mags, reverse=True)


def test_below_baseline_input_decreases_risk() -> None:
    """A driver below its baseline lowers risk — the sign is honest in both directions."""
    model = CycloneHazardModel()
    baseline = {"cyclone_alert_level": 3.0, "wind_speed_kmh": 150.0}
    drivers = {d.factor: d for d in model.explain(
        {"cyclone_alert_level": _col(1.0), "wind_speed_kmh": _col(20.0)}, baseline
    )}
    assert drivers["cyclone_alert_level"].direction == "decreases"
    assert drivers["wind_speed_kmh"].direction == "decreases"


def test_earthquake_override_is_exact_log_rate_decomposition() -> None:
    """Earthquake is Omori–Poisson, not logistic: its explain() decomposes the log-rate,
    and the two terms sum to exactly log(rate·decay)(input) − log(rate·decay)(baseline)."""
    model = EarthquakeImpactModel()
    baseline = {"mainshock_magnitude": 5.0, "days_since_mainshock": 5.0}
    m, d = 7.0, 0.5
    drivers = {dr.factor: dr for dr in model.explain(
        {"mainshock_magnitude": _col(m), "days_since_mainshock": _col(d)}, baseline
    )}
    # Bigger than baseline → magnitude increases; fresher than baseline → less decay,
    # so the elapsed-days term also increases risk.
    assert drivers["mainshock_magnitude"].direction == "increases"
    assert drivers["days_since_mainshock"].direction == "increases"

    # Exactness: reconstruct the true log-rate shift and compare to the summed contributions.
    def log_rate(mag: float, days: float) -> float:
        rate = model.daily_rate_scale * 10.0 ** (
            model.productivity_log10 * (mag - model.reference_magnitude)
        )
        decay = ((days + model.omori_c_days) / model.omori_c_days) ** (-model.omori_p)
        return math.log(rate * decay)

    expected_shift = log_rate(m, d) - log_rate(
        baseline["mainshock_magnitude"], baseline["days_since_mainshock"]
    )
    assert abs(sum(dr.contribution for dr in drivers.values()) - expected_shift) < 1e-9


def test_zero_deviation_is_neutral() -> None:
    """An input exactly at baseline contributes nothing — no phantom drivers."""
    model = WildfireHazardModel()
    drivers = model.explain({"temp_anomaly_c": _col(3.0)}, {"temp_anomaly_c": 3.0})
    assert drivers[0].contribution == 0.0 and drivers[0].direction == "neutral"


def test_every_driver_carries_the_uncalibrated_caveat() -> None:
    """No attribution may read as validated ground truth — every hazard, every driver."""
    cases = [
        (WildfireHazardModel(), {"temp_anomaly_c": _col(5.0)}, {"temp_anomaly_c": 0.0}),
        (FloodHazardModel(), {"precipitation_mm": _col(80.0)}, {"precipitation_mm": 0.0}),
        (CycloneHazardModel(), {"wind_speed_kmh": _col(120.0)}, {"wind_speed_kmh": 10.0}),
        (
            EarthquakeImpactModel(),
            {"mainshock_magnitude": _col(6.5)},
            {"mainshock_magnitude": 5.0},
        ),
    ]
    for model, inputs, baseline in cases:
        drivers = model.explain(inputs, baseline)
        assert drivers, f"{type(model).__name__} produced no driver"
        assert all(d.caveat == UNCALIBRATED_DRIVER_CAVEAT for d in drivers)
