"""Flood, quake, and cyclone screening — the Session-35 Tier 0 indexes.

Each index wraps its Session-35 hazard model exactly the way
:class:`~vectis.realtime.screening.wildfire.WildfireScreeningIndex` wraps the Session-7
logistic: **one vectorized evaluation per active cell** — a point estimate, no sampling,
no scenarios, no Monte Carlo, and no import of the simulation engine (the AST decoupling
test covers this module too).

Relevance gating (the no-fake-numbers rule, per hazard): a cell is screened only if it
carries the hazard's *own* observed driver — a ``flood_alert_level``/``precipitation_mm``
reading for flood, an ``earthquake_magnitude`` for quake, a ``cyclone_alert_level`` for
cyclone. Cells without it are **skipped**, never given a fabricated neutral score.
Unobserved *co*-drivers default to benign (0 mm, Green, calm wind) rather than to the
illustrative digital-twin baselines: unlike wildfire — where the twin baseline keeps the
screen comparable to the engine's base state — backfilling a wet/stormy baseline into
every cell on Earth would fabricate global flood/cyclone risk.

Honesty: these screens inherit their models' **illustrative, uncalibrated coefficients**
(see each model's module docstring). A screening score existing is not validation.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

import numpy as np

from vectis.realtime.events.base import CellId
from vectis.realtime.screening.base import ScreeningIndex, ScreeningScore, register
from vectis.realtime.state.models import WorldCellState
from vectis.simulation.models.cyclone import CycloneHazardModel, default_cyclone_model
from vectis.simulation.models.earthquake import (
    EarthquakeImpactModel,
    default_earthquake_model,
)
from vectis.simulation.models.flood import FloodHazardModel, default_flood_model

#: GDACS Green — the benign default for an unobserved alert-level co-driver.
_ALERT_GREEN = 1.0


class FloodScreeningIndex(ScreeningIndex):
    """Cheap flood risk index: the flood logistic evaluated once per cell, vectorized."""

    hazard = "flood"

    def __init__(self, model: FloodHazardModel | None = None) -> None:
        # Calibrated coefficients when an artifact exists, illustrative priors otherwise —
        # the same default seam the engine would use, so screen and engine agree.
        self.model = model or default_flood_model()

    def score(self, cells: Sequence[WorldCellState]) -> dict[CellId, ScreeningScore]:
        active = [
            c for c in cells
            if c.flood_alert_level is not None or c.precipitation_mm is not None
        ]
        if not active:
            return {}
        n = len(active)
        inputs = {
            "precipitation_mm": np.fromiter(
                (c.precipitation_mm or 0.0 for c in active), dtype=float, count=n
            ),
            "flood_alert_level": np.fromiter(
                (c.flood_alert_level or _ALERT_GREEN for c in active), dtype=float, count=n
            ),
        }
        risk = self.model.event_probability(inputs) * 100.0
        return {
            c.cell_id: ScreeningScore(self.hazard, float(v))
            for c, v in zip(active, risk, strict=True)
        }


class EarthquakeScreeningIndex(ScreeningIndex):
    """Cheap aftershock-impact index: the Omori-shaped model evaluated once per cell."""

    hazard = "quake"

    def __init__(self, model: EarthquakeImpactModel | None = None) -> None:
        self.model = model or default_earthquake_model()

    def score(self, cells: Sequence[WorldCellState]) -> dict[CellId, ScreeningScore]:
        active = [c for c in cells if c.earthquake_magnitude is not None]
        if not active:
            return {}
        now = datetime.now(UTC)
        n = len(active)
        inputs = {
            "mainshock_magnitude": np.fromiter(
                (c.earthquake_magnitude for c in active), dtype=float, count=n
            ),
            # ponytail: cell-level last_updated as "time since the quake" — any observation
            # refreshes it; add a per-variable timestamp if quake cells get chatty co-feeds.
            "days_since_mainshock": np.fromiter(
                (max((now - c.last_updated).total_seconds(), 0.0) / 86400.0 for c in active),
                dtype=float,
                count=n,
            ),
        }
        risk = self.model.event_probability(inputs) * 100.0
        return {
            c.cell_id: ScreeningScore(self.hazard, float(v))
            for c, v in zip(active, risk, strict=True)
        }


class CycloneScreeningIndex(ScreeningIndex):
    """Cheap cyclone risk index: the cyclone logistic evaluated once per cell, vectorized."""

    hazard = "cyclone"

    def __init__(self, model: CycloneHazardModel | None = None) -> None:
        self.model = model or default_cyclone_model()

    def score(self, cells: Sequence[WorldCellState]) -> dict[CellId, ScreeningScore]:
        active = [c for c in cells if c.cyclone_alert_level is not None]
        if not active:
            return {}
        n = len(active)
        inputs = {
            "cyclone_alert_level": np.fromiter(
                (c.cyclone_alert_level for c in active), dtype=float, count=n
            ),
            "wind_speed_kmh": np.fromiter(
                (c.extra.get("wind_speed_kmh", 0.0) for c in active), dtype=float, count=n
            ),
        }
        risk = self.model.event_probability(inputs) * 100.0
        return {
            c.cell_id: ScreeningScore(self.hazard, float(v))
            for c, v in zip(active, risk, strict=True)
        }


# Register the three Session-35 screens at import — joining wildfire in default_registry().
register(FloodScreeningIndex())
register(EarthquakeScreeningIndex())
register(CycloneScreeningIndex())


def demo() -> None:
    """Self-check: each screen ranks its hazard sensibly and skips irrelevant cells."""
    wet = WorldCellState(cell_id="wet", precipitation_mm=90.0, flood_alert_level=3.0)
    damp = WorldCellState(cell_id="damp", precipitation_mm=8.0)
    shaken = WorldCellState(cell_id="shaken", earthquake_magnitude=7.2)
    stormy = WorldCellState(cell_id="stormy", cyclone_alert_level=3.0, extra={"wind_speed_kmh": 150.0})
    bare = WorldCellState(cell_id="bare", temperature=20.0)  # wildfire-only cell
    cells = [wet, damp, shaken, stormy, bare]

    floods = FloodScreeningIndex().score(cells)
    assert set(floods) == {"wet", "damp"} and floods["wet"].value > floods["damp"].value
    quakes = EarthquakeScreeningIndex().score(cells)
    assert set(quakes) == {"shaken"} and 0.0 <= quakes["shaken"].value <= 100.0
    cyclones = CycloneScreeningIndex().score(cells)
    assert set(cyclones) == {"stormy"} and cyclones["stormy"].value > 50.0
    print("OK", {k: round(v.value, 1) for k, v in (floods | quakes | cyclones).items()})


if __name__ == "__main__":
    demo()
