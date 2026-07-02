"""Session 34 Step 3 — fitting the logistic and loading the coefficient artifact.

No real FIRMS/ERA5 history was reachable in this environment (no MAP_KEY), so these
tests fit against synthetic rows drawn from a *known* logistic — proving the fitter
recovers ground truth — exactly the offline-first convention the rest of the suite uses.
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pytest

from vectis.calibration.data.dataset import LabeledCellDay
from vectis.calibration.fit import (
    FITTED_FEATURES,
    fit_wildfire_coefficients,
    write_coefficients,
)
from vectis.simulation.models.wildfire import (
    _DEFAULT_COEFFICIENTS,
    WildfireHazardModel,
    default_wildfire_model,
)

#: Ground-truth logistic the synthetic rows are drawn from — deliberately different
#: from the illustrative priors, so "fitted" and "carried" are distinguishable.
_TRUE_INTERCEPT = -2.0
_TRUE_COEF = {"temp_anomaly_c": 0.4, "rainfall_anomaly_pct": -0.05, "wind_speed_kmh": 0.08}


def _synthetic_rows(n: int = 4000, seed: int = 34) -> list[LabeledCellDay]:
    rng = np.random.default_rng(seed)
    temp = rng.normal(0.0, 4.0, n)
    rain = rng.normal(0.0, 20.0, n)
    wind = rng.normal(15.0, 8.0, n)
    z = (
        _TRUE_INTERCEPT
        + _TRUE_COEF["temp_anomaly_c"] * temp
        + _TRUE_COEF["rainfall_anomaly_pct"] * rain
        + _TRUE_COEF["wind_speed_kmh"] * wind
    )
    fire = rng.random(n) < 1.0 / (1.0 + np.exp(-z))
    day0 = date(2020, 8, 1)
    return [
        LabeledCellDay(
            cell_id=f"cell{i}", day=day0 + timedelta(days=i % 30), lat=37.0, lon=-120.0,
            temp_anomaly_c=float(temp[i]), rainfall_anomaly_pct=float(rain[i]),
            wind_speed_kmh=float(wind[i]), fire=bool(fire[i]),
        )
        for i in range(n)
    ]


def test_fit_recovers_the_generating_coefficients() -> None:
    artifact = fit_wildfire_coefficients(_synthetic_rows())
    assert artifact["intercept"] == pytest.approx(_TRUE_INTERCEPT, abs=0.3)
    for feature in FITTED_FEATURES:
        assert artifact["coefficients"][feature] == pytest.approx(
            _TRUE_COEF[feature], abs=0.25 * max(1.0, abs(_TRUE_COEF[feature]))
        )


def test_unidentifiable_ignition_coefficient_is_carried_not_fit() -> None:
    artifact = fit_wildfire_coefficients(_synthetic_rows(n=500))
    assert artifact["coefficients"]["ignition_sources"] == _DEFAULT_COEFFICIENTS["ignition_sources"]
    assert artifact["carried_forward"] == {
        "ignition_sources": _DEFAULT_COEFFICIENTS["ignition_sources"]
    }
    assert "ignition_sources" not in artifact["features_fit"]


def test_fit_refuses_a_single_class_dataset() -> None:
    rows = [r for r in _synthetic_rows(n=200) if not r.fire]
    with pytest.raises(ValueError, match="both outcomes"):
        fit_wildfire_coefficients(rows)


def test_artifact_records_provenance_and_the_previous_priors() -> None:
    manifest = {"region": "california", "seed": 34}
    artifact = fit_wildfire_coefficients(_synthetic_rows(n=500), manifest=manifest)
    assert artifact["dataset_manifest"] == manifest
    assert artifact["illustrative_previous"]["coefficients"] == _DEFAULT_COEFFICIENTS
    assert artifact["n_rows"] == 500


def test_default_model_loads_the_artifact_when_present(tmp_path) -> None:
    artifact = fit_wildfire_coefficients(_synthetic_rows())
    path = write_coefficients(artifact, tmp_path / "calibration" / "wildfire_coefficients.json")

    model = default_wildfire_model(artifact_path=path)
    assert model.intercept == pytest.approx(artifact["intercept"])
    assert model.coefficients == pytest.approx(artifact["coefficients"])


def test_default_model_falls_back_to_the_illustrative_priors(tmp_path) -> None:
    model = default_wildfire_model(artifact_path=tmp_path / "nowhere.json")
    prior = WildfireHazardModel()
    assert model.intercept == prior.intercept
    assert model.coefficients == prior.coefficients
