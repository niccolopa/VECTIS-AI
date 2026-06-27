"""Concrete scenario generation for the wildfire climate-risk use case.

Implements :class:`~vectis.simulation.scenarios.base.ScenarioGenerator` with a
small, hand-specified set of weighted future branches, and provides a digital-twin
:class:`WorldState` factory for Liguria so the engine can be exercised end-to-end
before live State Estimation (NASA FIRMS / ERA5) is wired in.
"""

from __future__ import annotations

from vectis.simulation.scenarios.base import ScenarioGenerator
from vectis.simulation.schemas import (
    DistributionFamily,
    Scenario,
    ScenarioSet,
    StateVariable,
    WorldState,
)


def liguria_wildfire_state(region: str = "liguria") -> WorldState:
    """An illustrative current-state digital twin for the wildfire use case.

    Encodes the Session-7 example inputs *with uncertainty*: a +2 °C temperature
    anomaly, a -30 % rainfall anomaly, elevated wind, and a background ignition
    rate. ponytail: hand-set values — replace with ``StateEstimator`` output from
    live connectors (Session 8+).
    """
    return WorldState(
        region=region,
        variables=[
            StateVariable(
                name="temp_anomaly_c", value=2.0, family=DistributionFamily.NORMAL, std=0.5,
                unit="°C",
            ),
            StateVariable(
                name="rainfall_anomaly_pct", value=-30.0, family=DistributionFamily.NORMAL,
                std=8.0, unit="%",
            ),
            StateVariable(
                name="wind_speed_kmh", value=35.0, family=DistributionFamily.LOGNORMAL,
                std=0.25, unit="km/h",
            ),
            StateVariable(
                name="ignition_sources", value=1.5, family=DistributionFamily.POISSON,
                unit="count/day",
            ),
        ],
    )


class WildfireScenarioGenerator(ScenarioGenerator):
    """Branch the current state into three weighted wildfire futures.

    Priors encode our belief over which branch reality takes and sum to 1 (the
    :class:`ScenarioSet` enforces it). Bayesian updating will revise them as
    observations arrive (Session 8).
    """

    name = "wildfire_scenarios"

    def generate(self, state: WorldState) -> ScenarioSet:
        return ScenarioSet(
            scenarios=[
                Scenario(
                    id="baseline",
                    name="Baseline",
                    description="Current conditions persist over the horizon.",
                    prior=0.5,
                ),
                Scenario(
                    id="hotter_drier",
                    name="Hotter & Drier",
                    description="Heat-wave deepens and the rainfall deficit worsens.",
                    perturbations={"temp_anomaly_c": 1.5, "rainfall_anomaly_pct": -15.0},
                    prior=0.3,
                ),
                Scenario(
                    id="extreme_wind",
                    name="Extreme Wind",
                    description="Sustained high-wind event with more ignition sources.",
                    perturbations={"wind_speed_kmh": 20.0, "ignition_sources": 1.0},
                    prior=0.2,
                ),
            ]
        )
