"""``WildfireScreeningIndex`` — the one real screening implementation today.

Wraps the Session-7 :class:`~vectis.simulation.models.wildfire.WildfireHazardModel` and
evaluates its **vectorized logistic hazard once** per active cell: a single point estimate,
no sampling, no scenarios, no Monte Carlo. This is the deliberate cheap approximation that
stands in for the expensive engine until a cell is promoted (a future session).

Decoupling (important): this module imports the shared **hazard function**, never the
:class:`~vectis.simulation.engine.runner.VectorizedMonteCarloEngine`. Screening and
simulation are two independent code paths that happen to share the same logistic; the screen
must stay importable and fast without dragging in the sampler, the scenario set, or the
board. (Enforced by ``test_screening_does_not_import_the_monte_carlo_engine``.)

Reading the cell state
----------------------
The active cells are :class:`~vectis.realtime.state.models.WorldCellState` (the EMA path the
Session-31 global ingestion writes). It carries an absolute ``temperature`` (°C) and folds
``wind_speed_kmh`` into ``extra``. The hazard model wants a temperature **anomaly**, so we
subtract the same ~22 °C climatology baseline the pipeline's ``KALMAN_TO_WORLD`` bridge uses.
Model inputs a cell doesn't carry (rainfall anomaly, ignition sources) fall back to the
digital-twin climatology so the screen estimates the *same* quantity the full engine's base
state does — otherwise the two would approximate different things and the measured gap would
be meaningless.

A cell with no ``temperature`` has no wildfire-relevant state (e.g. it only ever got a GDACS
cyclone alert): it is **skipped**, not crashed and not given a fake neutral score.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from vectis.realtime.events.base import CellId
from vectis.realtime.screening.base import ScreeningIndex, ScreeningScore, register
from vectis.realtime.state.models import WorldCellState
from vectis.simulation.models.wildfire import WildfireHazardModel, default_wildfire_model

#: Seasonal climatology the absolute temperature reading is measured against, to recover the
#: anomaly the logistic expects. Mirrors ``pipeline.KALMAN_TO_WORLD``'s -22 °C offset.
#: ponytail: hand-set baseline — wire to per-cell climatology when calibration lands.
_CLIMATOLOGY_TEMP_C = 22.0

#: Baseline for model inputs a cell does not observe, taken from ``california_wildfire_state``
#: so screening approximates the same hazard the full engine's base state evaluates.
#: ponytail: fold rainfall/ignition into WorldCellState when feeds carry them, then drop these.
_BASELINE_INPUTS: dict[str, float] = {
    "wind_speed_kmh": 35.0,
    "rainfall_anomaly_pct": -30.0,
    "ignition_sources": 1.5,
}


class WildfireScreeningIndex(ScreeningIndex):
    """Cheap wildfire risk index: the logistic hazard evaluated once per cell, vectorized."""

    hazard = "wildfire"

    def __init__(self, model: WildfireHazardModel | None = None) -> None:
        # Calibrated coefficients when the Session-34 artifact exists, priors otherwise —
        # the same default the engine uses, so screen and engine estimate the same hazard.
        self.model = model or default_wildfire_model()

    def score(self, cells: Sequence[WorldCellState]) -> dict[CellId, ScreeningScore]:
        # Keep only cells with wildfire-relevant state (a temperature reading). The rest —
        # e.g. cyclone-only GDACS cells — are skipped, never fabricated.
        active = [c for c in cells if c.temperature is not None]
        if not active:
            return {}

        # Build the hazard's input columns in ONE array pass — no per-cell Python math.
        temp = np.fromiter((c.temperature for c in active), dtype=float, count=len(active))
        wind = np.fromiter(
            (c.extra.get("wind_speed_kmh", _BASELINE_INPUTS["wind_speed_kmh"]) for c in active),
            dtype=float,
            count=len(active),
        )
        ones = np.ones(len(active), dtype=float)
        inputs = {
            "temp_anomaly_c": temp - _CLIMATOLOGY_TEMP_C,
            "wind_speed_kmh": wind,
            "rainfall_anomaly_pct": ones * _BASELINE_INPUTS["rainfall_anomaly_pct"],
            "ignition_sources": ones * _BASELINE_INPUTS["ignition_sources"],
        }
        risk = self.model.event_probability(inputs) * 100.0  # 0–1 → shared 0–100 scale

        return {
            c.cell_id: ScreeningScore(self.hazard, float(v))
            for c, v in zip(active, risk, strict=True)
        }


# Register the one real screen at import — this is what populates default_registry().
register(WildfireScreeningIndex())


def demo() -> None:
    """Self-check: a hot/dry cell screens higher than a mild one; a stateless cell is skipped."""
    hot = WorldCellState(cell_id="hot", temperature=32.0, extra={"wind_speed_kmh": 45.0})
    mild = WorldCellState(cell_id="mild", temperature=18.0, extra={"wind_speed_kmh": 5.0})
    cyclone_only = WorldCellState(cell_id="cyc")  # no temperature → not wildfire-relevant

    scores = WildfireScreeningIndex().score([hot, mild, cyclone_only])
    assert "cyc" not in scores, "a cell with no wildfire state must be skipped, not scored"
    assert scores["hot"].value > scores["mild"].value, scores
    assert 0.0 <= scores["mild"].value <= 100.0
    print("OK", {k: round(v.value, 1) for k, v in scores.items()})


if __name__ == "__main__":
    demo()
