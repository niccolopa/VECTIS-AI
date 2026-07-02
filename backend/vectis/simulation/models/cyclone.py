"""Cyclone hazard — vectorized logistic over GDACS alert state and wind.

Maps sampled cyclone-related inputs to a per-sample impact probability via the same
vectorized-logistic form as wildfire and flood::

    P(cyclone impact) = sigmoid(intercept + Σ coefᵢ · inputᵢ)

Drivers (matching the structured cell-state fields real feeds populate):

- ``cyclone_alert_level`` — the GDACS cyclone alert ordinal (Green/Orange/Red → 1/2/3,
  Session-31 :class:`GdacsConnector`).
- ``wind_speed_kmh`` — observed wind speed (Open-Meteo weather feed).

Honesty (read before trusting a number): the coefficients below are **illustrative,
hand-set priors — no cyclone model in this repo has ever been fitted against real cyclone
impact labels.** Exactly like wildfire's Session-7 priors, they exist so the architecture
can be exercised end to end; a future calibration run drops fitted parameters into
``artifacts/calibration/cyclone_coefficients.json`` and :func:`default_cyclone_model`
picks them up through the shared
:func:`~vectis.simulation.models.base.load_calibrated_or_default` seam with zero code
change. This model's existence is not validation.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from scipy.special import expit

from vectis.simulation.models.base import HazardModel, load_calibrated_or_default
from vectis.simulation.scenarios.base import ScenarioGenerator
from vectis.simulation.schemas import (
    DistributionFamily,
    Scenario,
    ScenarioSet,
    StateVariable,
    WorldState,
)

# ponytail: illustrative log-odds coefficients — higher alert and stronger wind → higher risk.
# NOT fitted against any real cyclone record; replaced only by a real calibration artifact.
_DEFAULT_COEFFICIENTS: dict[str, float] = {
    "cyclone_alert_level": 1.6,  # per GDACS alert step (1=Green … 3=Red)
    "wind_speed_kmh": 0.025,  # per km/h of observed wind
}


@dataclass(frozen=True)
class CycloneHazardModel(HazardModel):
    """Logistic cyclone hazard over GDACS alert-level and wind drivers."""

    intercept: float = -7.0
    coefficients: Mapping[str, float] = field(
        default_factory=lambda: dict(_DEFAULT_COEFFICIENTS)
    )

    def event_probability(self, inputs: Mapping[str, np.ndarray]) -> np.ndarray:
        if not inputs:
            return np.empty(0, dtype=float)
        size = len(next(iter(inputs.values())))
        z = np.full(size, self.intercept, dtype=float)
        for name, coef in self.coefficients.items():
            column = inputs.get(name)
            if column is not None:
                z = z + coef * column
        return np.asarray(expit(z), dtype=float)


def default_cyclone_model(artifact_path: Path | None = None) -> CycloneHazardModel:
    """Calibrated cyclone coefficients when an artifact exists; the illustrative priors
    above otherwise (the honest state of this repo — see the module docstring)."""
    return load_calibrated_or_default("cyclone", CycloneHazardModel, artifact_path)


def approaching_cyclone_state(region: str = "luzon_strait") -> WorldState:
    """An illustrative current-state digital twin for the cyclone use case.

    ponytail: hand-set values (an Orange GDACS alert with strengthening wind) — in the
    live path the pipeline projects real cell state over this baseline, as with wildfire.
    """
    return WorldState(
        region=region,
        variables=[
            StateVariable(
                name="cyclone_alert_level", value=2.0, family=DistributionFamily.NORMAL,
                std=0.3, unit="GDACS level",
            ),
            StateVariable(
                name="wind_speed_kmh", value=85.0, family=DistributionFamily.NORMAL,
                std=15.0, unit="km/h",
            ),
        ],
    )


class CycloneScenarioGenerator(ScenarioGenerator):
    """Branch the current state into three weighted cyclone futures (wildfire's pattern)."""

    name = "cyclone_scenarios"

    def generate(self, state: WorldState) -> ScenarioSet:
        return ScenarioSet(
            scenarios=[
                Scenario(
                    id="baseline",
                    name="Baseline Track",
                    description="The system holds its current intensity and track.",
                    prior=0.5,
                ),
                Scenario(
                    id="intensification_landfall",
                    name="Intensification at Landfall",
                    description="The system intensifies and the alert escalates to Red.",
                    perturbations={"cyclone_alert_level": 1.0, "wind_speed_kmh": 40.0},
                    prior=0.3,
                ),
                Scenario(
                    id="recurvature",
                    name="Recurvature Out to Sea",
                    description="The system recurves away and weakens.",
                    perturbations={"cyclone_alert_level": -1.0, "wind_speed_kmh": -30.0},
                    prior=0.2,
                ),
            ]
        )


def demo() -> None:
    """Self-check: higher-alert/stronger-wind inputs raise the probability; priors branch."""
    model = default_cyclone_model()
    calm = model.event_probability(
        {"cyclone_alert_level": np.array([1.0]), "wind_speed_kmh": np.array([15.0])}
    )
    landfall = model.event_probability(
        {"cyclone_alert_level": np.array([3.0]), "wind_speed_kmh": np.array([160.0])}
    )
    assert 0.0 <= calm[0] < 0.1 < 0.8 < landfall[0] <= 1.0, (calm, landfall)

    scenarios = CycloneScenarioGenerator().generate(approaching_cyclone_state())
    assert abs(sum(s.prior for s in scenarios.scenarios) - 1.0) < 1e-9
    print("OK", round(float(calm[0]), 4), round(float(landfall[0]), 4))


if __name__ == "__main__":
    demo()
