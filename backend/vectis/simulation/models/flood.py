"""Flood hazard — vectorized logistic over precipitation-related state.

Maps sampled hydrological inputs to a per-sample flood probability via the same
vectorized-logistic form as wildfire::

    P(flood) = sigmoid(intercept + Σ coefᵢ · inputᵢ)

Drivers (matching the structured cell-state fields real feeds populate):

- ``precipitation_mm`` — recent precipitation accumulation (Open-Meteo weather feed).
- ``flood_alert_level`` — the GDACS flood alert ordinal (Green/Orange/Red → 1/2/3,
  Session-31 :class:`GdacsConnector`).

Honesty (read before trusting a number): the coefficients below are **illustrative,
hand-set priors — no flood model in this repo has ever been fitted against real flood
labels.** Exactly like wildfire's Session-7 priors, they exist so the architecture can be
exercised end to end; a future calibration run drops fitted parameters into
``artifacts/calibration/flood_coefficients.json`` and :func:`default_flood_model` picks
them up through the shared :func:`~vectis.simulation.models.base.load_calibrated_or_default`
seam with zero code change. This model's existence is not validation.
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

# ponytail: illustrative log-odds coefficients — wetter and higher-alerted → higher risk.
# NOT fitted against any real flood record; replaced only by a real calibration artifact.
_DEFAULT_COEFFICIENTS: dict[str, float] = {
    "precipitation_mm": 0.045,  # per mm of recent accumulation
    "flood_alert_level": 1.1,  # per GDACS alert step (1=Green … 3=Red)
}


@dataclass(frozen=True)
class FloodHazardModel(HazardModel):
    """Logistic flood hazard over precipitation and alert-level drivers."""

    intercept: float = -5.0
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


def default_flood_model(artifact_path: Path | None = None) -> FloodHazardModel:
    """Calibrated flood coefficients when an artifact exists; the illustrative priors
    above otherwise (the honest state of this repo — see the module docstring)."""
    return load_calibrated_or_default("flood", FloodHazardModel, artifact_path)


def monsoon_flood_state(region: str = "bengal_delta") -> WorldState:
    """An illustrative current-state digital twin for the flood use case.

    ponytail: hand-set values (a wet spell with an Orange GDACS alert) — in the live
    path the pipeline projects real cell state over this baseline, as with wildfire.
    """
    return WorldState(
        region=region,
        variables=[
            StateVariable(
                name="precipitation_mm", value=45.0, family=DistributionFamily.NORMAL,
                std=12.0, unit="mm",
            ),
            StateVariable(
                name="flood_alert_level", value=2.0, family=DistributionFamily.NORMAL,
                std=0.3, unit="GDACS level",
            ),
        ],
    )


class FloodScenarioGenerator(ScenarioGenerator):
    """Branch the current state into three weighted flood futures (wildfire's pattern)."""

    name = "flood_scenarios"

    def generate(self, state: WorldState) -> ScenarioSet:
        return ScenarioSet(
            scenarios=[
                Scenario(
                    id="baseline",
                    name="Baseline",
                    description="Current precipitation regime persists over the horizon.",
                    prior=0.5,
                ),
                Scenario(
                    id="sustained_deluge",
                    name="Sustained Deluge",
                    description="The rain band stalls; accumulation deepens and alerts escalate.",
                    perturbations={"precipitation_mm": 40.0, "flood_alert_level": 1.0},
                    prior=0.3,
                ),
                Scenario(
                    id="clearing",
                    name="Clearing",
                    description="The system moves through; accumulation tapers off.",
                    perturbations={"precipitation_mm": -25.0},
                    prior=0.2,
                ),
            ]
        )


def demo() -> None:
    """Self-check: wetter/higher-alert inputs raise the probability; priors branch validly."""
    model = default_flood_model()
    dry = model.event_probability({"precipitation_mm": np.array([2.0]), "flood_alert_level": np.array([1.0])})
    wet = model.event_probability({"precipitation_mm": np.array([110.0]), "flood_alert_level": np.array([3.0])})
    assert 0.0 <= dry[0] < 0.1 < 0.9 < wet[0] <= 1.0, (dry, wet)

    scenarios = FloodScenarioGenerator().generate(monsoon_flood_state())
    assert abs(sum(s.prior for s in scenarios.scenarios) - 1.0) < 1e-9
    print("OK", round(float(dry[0]), 4), round(float(wet[0]), 4))


if __name__ == "__main__":
    demo()
