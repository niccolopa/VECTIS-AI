"""Deterministic state transitions — how an observation *evolves* a twin's present.

When real data arrives, two distinct things happen:
1. **Belief** about the future is revised (Bayesian update — Session 8).
2. The **present physical state** moves (it actually rained; the temperature
   actually rose). That second part is *deterministic* and lives here.

Transitions are simple, auditable **heuristics** — explicitly *not* a physics
engine (no fluid dynamics, no PDE solvers). A :class:`StateTransition` mutates a
twin's state in place and reports whether anything changed, so the twin can decide
whether the change is worth a Monte Carlo re-run.

Pure arithmetic — no LLM, no I/O.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from vectis.simulation.probability.bayesian import Observation

if TYPE_CHECKING:  # avoid a runtime import cycle (region imports this module)
    from vectis.digital_twin.entities.region import RegionState


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


class StateTransition(ABC):
    """A deterministic rule that evolves a twin's physical state from an observation."""

    @abstractmethod
    def apply(self, state: RegionState, observation: Observation) -> bool:
        """Mutate ``state`` in place; return ``True`` iff anything changed."""
        raise NotImplementedError


# Variable-name aliases the climate transition recognizes (observations may name
# the same quantity differently depending on the upstream feed).
_TEMP_KEYS = {"temp_anomaly_c", "temperature_anomaly", "temperature"}
_HUMIDITY_KEYS = {"humidity_level", "humidity"}
_RAIN_PCT_KEYS = {"rainfall_anomaly_pct"}
_RAIN_MM_KEYS = {"rainfall_mm", "precipitation_mm"}
_FIRE_KEYS = {"active_fires", "fire_detections", "ignition_sources"}


class ClimateTransition(StateTransition):
    """Heuristic climate dynamics for a :class:`RegionTwin`.

    Rules (deliberately simple, tunable):
    - A temperature/humidity/rain observation sets that physical field directly.
    - A fire-detection observation accumulates ``recent_fire_history``.
    - Vegetation stress then relaxes toward the heat/moisture balance:
      ``Δstress = temp_anomaly · K_TEMP − humidity · K_HUM`` — heat dries fuel out,
      moisture relieves it. Only recomputed when a *driver* (temp/humidity) moved,
      so an unrelated observation can't drift the stress index.

    ``K_TEMP``/``K_HUM`` are balanced so the California default state (≈ +2 °C anomaly,
    20 % humidity) sits at equilibrium (Δstress = 0). ponytail: hand-tuned heuristic
    — replace coefficients with a fitted model once real labels exist.
    """

    K_TEMP: float = 1.0
    K_HUM: float = 0.1

    def apply(self, state: RegionState, observation: Observation) -> bool:
        var, value = observation.variable, observation.value
        driver_moved = False
        changed = False

        if var in _TEMP_KEYS:
            changed = changed or state.temperature_anomaly != value
            state.temperature_anomaly = value
            driver_moved = True
        elif var in _HUMIDITY_KEYS:
            changed = changed or state.humidity_level != value
            state.humidity_level = value
            driver_moved = True
        elif var in _RAIN_PCT_KEYS:
            # rainfall anomaly maps to absolute humidity (inverse of the twin's
            # WorldState mapping rainfall = humidity − 50).
            new_h = _clamp(value + 50.0, 0.0, 100.0)
            changed = changed or state.humidity_level != new_h
            state.humidity_level = new_h
            driver_moved = True
        elif var in _RAIN_MM_KEYS:
            new_h = _clamp(state.humidity_level + value, 0.0, 100.0)
            changed = changed or state.humidity_level != new_h
            state.humidity_level = new_h
            driver_moved = True
        elif var in _FIRE_KEYS:
            state.recent_fire_history += value
            changed = True

        if driver_moved:
            delta = state.temperature_anomaly * self.K_TEMP - state.humidity_level * self.K_HUM
            new_stress = _clamp(state.vegetation_stress + delta, 0.0, 100.0)
            if new_stress != state.vegetation_stress:
                state.vegetation_stress = new_stress
                changed = True

        return changed
