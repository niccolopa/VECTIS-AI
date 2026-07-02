"""Concrete, versioned world-state models — the "present" of VECTIS V3.

Session 16 defined :class:`~vectis.realtime.state.base.CellState`, a generic
mean/covariance belief shaped for a Kalman filter. This module adds the **concrete,
domain-named** cell state the running engine actually carries: the climate variables a
wildfire-risk cell tracks, plus first-class **versioning** so every transition is
auditable and the history is replayable.

Why a second model instead of editing the blueprint: the covariance representation is
the eventual Kalman target; this is the working state the Session-19 :class:`StateUpdater`
merges observations into today (EMA / overwrite, per the brief). They coexist — the
blueprint is the math target, this is the present.

Pure data containers. No computation, no LLM — the Math Firewall holds.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from vectis.realtime.events.base import CellId


def _utcnow() -> datetime:
    return datetime.now(UTC)


class WorldCellState(BaseModel):
    """The present state of one grid cell — the variables plus version metadata.

    A cell tracks the observed variables that drive hazard risk — the wildfire climate
    set plus, since Session 35, the multi-hazard fields the real USGS/GDACS/weather feeds
    report (magnitude, alert levels, precipitation). Each is optional (``None`` until a
    feed has reported it) so a freshly-materialized cell is honest about what it has and
    hasn't seen, rather than faking a zero reading.

    ``version`` increments on every applied observation and ``last_updated`` stamps it,
    so any historical version is an exact, auditable snapshot of the cell at that time.
    """

    cell_id: CellId = Field(description="Grid cell this state describes.")

    # --- tracked variables (None = not yet observed) ---
    temperature: float | None = Field(default=None, description="Temperature / anomaly, °C.")
    humidity: float | None = Field(default=None, description="Relative humidity, %.")
    drought_index: float | None = Field(default=None, description="Drought severity index.")
    fire_risk: float | None = Field(default=None, description="Estimated fire risk, 0–100.")

    # --- multi-hazard variables the Session-31 real feeds report (Session 35) ---
    precipitation_mm: float | None = Field(
        default=None, description="Recent precipitation accumulation, mm (weather feed)."
    )
    earthquake_magnitude: float | None = Field(
        default=None, description="Most recent reported mainshock magnitude (USGS)."
    )
    flood_alert_level: float | None = Field(
        default=None, description="GDACS flood alert ordinal: 1=Green, 2=Orange, 3=Red."
    )
    cyclone_alert_level: float | None = Field(
        default=None, description="GDACS cyclone alert ordinal: 1=Green, 2=Orange, 3=Red."
    )

    # Catch-all for canonical variables outside the four named ones, so an observation is
    # never silently dropped before forecasting can use it.
    extra: dict[str, float] = Field(default_factory=dict, description="Other observed variables.")

    # --- versioning / provenance ---
    version: int = Field(default=0, ge=0, description="Monotonic revision; +1 per observation.")
    last_updated: datetime = Field(default_factory=_utcnow, description="When this version was written.")
    sources: list[str] = Field(default_factory=list, description="Feeds that have shaped this cell.")
