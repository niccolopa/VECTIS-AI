"""Earthquake impact hazard — Omori-shaped aftershock/shaking-impact probability.

This is explicitly **not mainshock prediction** (nobody can do that). It is the far more
modest, physically-grounded question: *given a real, already-observed mainshock* (the USGS
magnitude Session 31's :class:`UsgsQuakeConnector` already ingests), how likely is a
damaging aftershock / continued shaking impact over the near horizon? Vectorized::

    rate(t)  = daily_rate_scale · 10^(productivity_log10 · (M − reference_magnitude))
               · ((t + c) / c)^(−p)                      # Omori–Utsu-shaped decay, 1 at t=0
    P(event) = 1 − exp(−rate(t))                         # Poisson exceedance over the horizon

Drivers (matching the structured cell-state fields real feeds populate):

- ``mainshock_magnitude`` — the reported USGS magnitude of the recent mainshock.
- ``days_since_mainshock`` — elapsed time driving the Omori decay (clamped to ≥ 0).

Honesty (read before trusting a number): the parameters below are **illustrative,
hand-set priors — not geophysically precise, and never fitted against a real aftershock
catalog.** The Omori–Utsu *shape* is the standard empirical form, but real ``p``/``c``/
productivity values vary by region and sequence; these exist so the architecture can be
exercised end to end. A future calibration run drops fitted parameters into
``artifacts/calibration/earthquake_coefficients.json`` and :func:`default_earthquake_model`
picks them up through the shared
:func:`~vectis.simulation.models.base.load_calibrated_or_default` seam with zero code
change. This model's existence is not validation.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from vectis.simulation.models.base import HazardModel, load_calibrated_or_default
from vectis.simulation.scenarios.base import ScenarioGenerator
from vectis.simulation.schemas import (
    DistributionFamily,
    Scenario,
    ScenarioSet,
    StateVariable,
    WorldState,
)


@dataclass(frozen=True)
class EarthquakeImpactModel(HazardModel):
    """Omori-shaped aftershock/impact probability conditioned on a recent real mainshock.

    ponytail: illustrative parameters — Omori–Utsu shape with hand-set constants, NOT a
    regional aftershock fit; replaced only by a real calibration artifact.
    """

    reference_magnitude: float = 5.0  #: magnitude at which the base daily rate applies
    productivity_log10: float = 0.9  #: log10 rate gain per magnitude unit above reference
    omori_c_days: float = 0.05  #: Omori c — softens the t=0 singularity
    omori_p: float = 1.1  #: Omori p — decay exponent (>1 ⇒ rate integrates finitely)
    daily_rate_scale: float = 0.15  #: expected damaging events/day at reference mag, t=0

    def event_probability(self, inputs: Mapping[str, np.ndarray]) -> np.ndarray:
        if not inputs:
            return np.empty(0, dtype=float)
        size = len(next(iter(inputs.values())))
        magnitude = np.asarray(
            inputs.get("mainshock_magnitude", np.zeros(size)), dtype=float
        )
        # Sampling noise can push elapsed time negative — physically it is ≥ 0.
        days = np.maximum(
            np.asarray(inputs.get("days_since_mainshock", np.zeros(size)), dtype=float), 0.0
        )
        rate = self.daily_rate_scale * np.power(
            10.0, self.productivity_log10 * (magnitude - self.reference_magnitude)
        )
        decay = np.power((days + self.omori_c_days) / self.omori_c_days, -self.omori_p)
        return np.asarray(1.0 - np.exp(-rate * decay), dtype=float)


def default_earthquake_model(artifact_path: Path | None = None) -> EarthquakeImpactModel:
    """Calibrated aftershock parameters when an artifact exists; the illustrative priors
    above otherwise (the honest state of this repo — see the module docstring)."""
    return load_calibrated_or_default("earthquake", EarthquakeImpactModel, artifact_path)


def aftershock_state(region: str = "honshu_offshore") -> WorldState:
    """An illustrative current-state digital twin for the aftershock use case.

    ponytail: hand-set values (a fresh M6.8 mainshock) — in the live path the pipeline
    projects real USGS cell state over this baseline, as with wildfire.
    """
    return WorldState(
        region=region,
        variables=[
            StateVariable(
                name="mainshock_magnitude", value=6.8, family=DistributionFamily.NORMAL,
                std=0.3, unit="Mw",
            ),
            StateVariable(
                name="days_since_mainshock", value=1.0, family=DistributionFamily.NORMAL,
                std=0.25, unit="days",
            ),
        ],
    )


class EarthquakeScenarioGenerator(ScenarioGenerator):
    """Branch the current state into three weighted aftershock futures (wildfire's pattern)."""

    name = "earthquake_scenarios"

    def generate(self, state: WorldState) -> ScenarioSet:
        return ScenarioSet(
            scenarios=[
                Scenario(
                    id="baseline",
                    name="Baseline Decay",
                    description="The sequence decays along the typical Omori curve.",
                    prior=0.6,
                ),
                Scenario(
                    id="energetic_sequence",
                    name="Energetic Sequence",
                    description="A large aftershock re-energizes the sequence "
                    "(effective magnitude steps up).",
                    perturbations={"mainshock_magnitude": 0.6},
                    prior=0.25,
                ),
                Scenario(
                    id="rapid_quiescence",
                    name="Rapid Quiescence",
                    description="The sequence shuts off faster than typical decay.",
                    perturbations={"days_since_mainshock": 3.0},
                    prior=0.15,
                ),
            ]
        )


def demo() -> None:
    """Self-check: bigger/fresher mainshocks raise the probability; priors branch validly."""
    model = default_earthquake_model()
    small_old = model.event_probability(
        {"mainshock_magnitude": np.array([4.5]), "days_since_mainshock": np.array([10.0])}
    )
    big_fresh = model.event_probability(
        {"mainshock_magnitude": np.array([7.5]), "days_since_mainshock": np.array([0.1])}
    )
    assert 0.0 <= small_old[0] < 0.05 < 0.5 < big_fresh[0] <= 1.0, (small_old, big_fresh)

    # Monotone in magnitude and (inversely) in elapsed days, vectorized in one pass.
    mags = model.event_probability(
        {"mainshock_magnitude": np.array([5.0, 6.0, 7.0]), "days_since_mainshock": np.ones(3)}
    )
    assert np.all(np.diff(mags) > 0), mags
    ages = model.event_probability(
        {"mainshock_magnitude": np.full(3, 6.5), "days_since_mainshock": np.array([0.5, 2.0, 8.0])}
    )
    assert np.all(np.diff(ages) < 0), ages

    scenarios = EarthquakeScenarioGenerator().generate(aftershock_state())
    assert abs(sum(s.prior for s in scenarios.scenarios) - 1.0) < 1e-9
    print("OK", round(float(small_old[0]), 4), round(float(big_fresh[0]), 4))


if __name__ == "__main__":
    demo()
