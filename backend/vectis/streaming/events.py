"""Wire-format models for the real-time layer.

Two directions cross the API boundary:

- **Inbound** — real-world events (:class:`SensorReading`, :class:`WeatherAlert`)
  posted to ``/stream/ingest``. They are a tagged union (``kind`` discriminator)
  and each knows how to translate itself into the Session-8
  :class:`~vectis.simulation.probability.bayesian.Observation` the math layer
  speaks. Events are *transport* concepts; ``Observation`` is the *math* concept —
  keeping them separate means the engine never depends on the wire format.
- **Outbound** — :class:`RiskState` (the current belief) and :class:`StateChange`
  (the broadcast notification emitted after an event is processed).

Pure data containers — no computation, no LLM.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field

# RiskState now lives in the digital_twin layer (it is a twin's computed output);
# re-exported here so existing `from vectis.streaming.events import RiskState` holds.
from vectis.digital_twin.schemas import RiskState
from vectis.simulation.probability.bayesian import Observation

__all__ = [
    "IngestEvent",
    "RiskState",
    "SensorReading",
    "StateChange",
    "StreamEvent",
    "WeatherAlert",
]


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _event_id() -> str:
    return uuid.uuid4().hex


# ── Inbound events ───────────────────────────────────────────────────────────
class StreamEvent(BaseModel):
    """Base class for an incoming real-world event."""

    event_id: str = Field(default_factory=_event_id)
    source: str = Field(description="Originating system/station identifier.")
    region: str = Field(
        default="liguria", description="Digital-twin id this event is routed to."
    )
    observed_at: datetime = Field(default_factory=_utcnow)

    def to_observation(self) -> Observation:
        """Translate this event into a math-layer :class:`Observation`."""
        raise NotImplementedError

    def dedupe_key(self) -> str:
        """Content signature for debouncing (ignores ``event_id``/timestamp).

        Two events with the same key carry the *same measurement* and must not be
        double-counted by the Bayesian update (see ``updater.py`` debouncing).
        """
        obs = self.to_observation()
        return f"{self.region}:{self.source}:{obs.variable}:{obs.value:.6g}"


class SensorReading(StreamEvent):
    """A scalar measurement from a field sensor (weather station, FWI probe…)."""

    kind: Literal["sensor_reading"] = "sensor_reading"
    variable: str = Field(description="WorldState variable name this reading maps to.")
    value: float
    std: float | None = Field(
        default=None, ge=0.0, description="Measurement uncertainty (1σ), if known."
    )

    def to_observation(self) -> Observation:
        return Observation(variable=self.variable, value=self.value, std=self.std)


# Alert severity → measurement confidence. A "critical" alert is a high-confidence
# statement about the variable, so it is given a tight std (it should move beliefs
# hard); an "info" alert is soft. ponytail: simple lookup — tune against real feeds.
_SEVERITY_STD: dict[str, float] = {"info": 1.0, "warning": 0.5, "critical": 0.2}


class WeatherAlert(StreamEvent):
    """An official alert (e.g. heat-wave/red-flag warning) about a variable."""

    kind: Literal["weather_alert"] = "weather_alert"
    variable: str
    value: float = Field(description="Asserted value of the variable under the alert.")
    severity: Literal["info", "warning", "critical"] = "warning"

    def to_observation(self) -> Observation:
        return Observation(
            variable=self.variable, value=self.value, std=_SEVERITY_STD[self.severity]
        )


#: Discriminated union FastAPI validates the ingest body against.
IngestEvent = Annotated[SensorReading | WeatherAlert, Field(discriminator="kind")]


# ── Outbound state ───────────────────────────────────────────────────────────
class StateChange(BaseModel):
    """Broadcast payload emitted when an event changes the risk picture."""

    type: Literal["state_changed"] = "state_changed"
    event_id: str
    triggered_rerun: bool = Field(
        description="Whether the belief shift was large enough to re-run Monte Carlo."
    )
    belief_shift: float = Field(
        ge=0.0, description="Total-variation distance between prior and posterior beliefs."
    )
    risk: RiskState
