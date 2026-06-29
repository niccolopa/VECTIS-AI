"""Weather connector — temperature/humidity/wind readings into V3 events.

Mirrors a typical weather JSON API (OpenWeatherMap-style ``{"main": {"temp": ...},
"wind": {"speed": ...}}`` is common, but we accept the flat ``{"temperature",
"humidity", "wind"}`` shape too). Each reading fans out into one
:class:`~vectis.realtime.events.base.GlobalEvent` per measured variable, so every
event maps cleanly to a single canonical :class:`GlobalObservation`.
"""

from __future__ import annotations

from typing import Any

from vectis.realtime.connectors.base import BaseAPIConnector
from vectis.realtime.events.base import GeoPoint, GlobalEvent, GlobalObservation, naive_cell_id

# Map raw payload keys to the canonical WorldState variable they normalize to.
# ``offset`` converts an absolute reading to the anomaly the model expects (0 = identity;
# ponytail: hand-set baselines — wire these to per-cell climatology when it lands).
_VARIABLE_MAP: dict[str, tuple[str, float]] = {
    "temperature": ("temp_anomaly_c", 0.0),
    "humidity": ("humidity_pct", 0.0),
    "wind": ("wind_speed_kmh", 0.0),
}


class WeatherEvent(GlobalEvent):
    """One weather measurement (a single variable) from a weather feed."""

    def to_observation(self) -> GlobalObservation:
        variable = self.payload["variable"]
        return GlobalObservation(
            cell_id=self.cell_id or naive_cell_id(self.location),
            variable=variable,
            value=float(self.payload["value"]),
            std=self.payload.get("std"),
            observed_at=self.observed_at,
            source=self.source,
        )


class WeatherAPIConnector(BaseAPIConnector):
    """Fetch a current-conditions reading for a location and normalize it.

    Offline-safe: with no ``base_url`` it returns a deterministic synthetic reading so
    the ingestion layer runs with no network or API key.
    """

    source = "weather_api"

    def __init__(self, *, location: GeoPoint | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.location = location or GeoPoint(lat=44.41, lon=8.93)  # Liguria default

    def fetch(self) -> dict[str, Any]:
        if not self.base_url:
            # Deterministic offline reading (hot, dry, breezy — a plausible fire day).
            return {"temperature": 34.0, "humidity": 20.0, "wind": 25.0}
        return self.get_json(f"{self.base_url}/current", params={"lat": self.location.lat, "lon": self.location.lon})

    def normalize(self, raw: dict[str, Any]) -> list[GlobalEvent]:
        events: list[GlobalEvent] = []
        for key, (variable, offset) in _VARIABLE_MAP.items():
            if raw.get(key) is None:
                continue
            events.append(
                WeatherEvent(
                    source=self.source,
                    location=self.location,
                    payload={"variable": variable, "value": float(raw[key]) - offset},
                )
            )
        return events
