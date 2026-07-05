"""Weather connector — live temperature/humidity/wind readings into V3 events.

Fetches **current conditions from Open-Meteo** (``https://api.open-meteo.com/v1/forecast``),
an open weather API that requires **no API key** — so a fresh clone streams real California
weather with zero setup. Each reading fans out into one
:class:`~vectis.realtime.events.base.GlobalEvent` per measured variable (temperature,
humidity, wind, and a derived drought index), so every event maps cleanly to a single
canonical :class:`GlobalObservation`.

Offline-safe: if Open-Meteo is unreachable (no network) the connector logs a warning and
serves a deterministic synthetic reading, so the live risk engine never stalls or crashes.
"""

from __future__ import annotations

from typing import Any

from vectis.core.logging import get_logger
from vectis.realtime.connectors.base import BaseAPIConnector, ConnectorError
from vectis.realtime.events.base import GeoPoint, GlobalEvent, GlobalObservation
from vectis.realtime.state.cell_id import assign_cell_id

logger = get_logger(__name__)

# Open-Meteo current-conditions endpoint (keyless, open data). Defaults: °C, %, km/h —
# which already match the canonical WorldState units below, so no unit conversion is needed.
_OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
_OPEN_METEO_CURRENT = "temperature_2m,relative_humidity_2m,wind_speed_10m,precipitation"

# Map raw payload keys to the canonical WorldState variable they normalize to.
# ``offset`` converts an absolute reading to the anomaly the model expects (0 = identity;
# ponytail: hand-set baselines — wire these to per-cell climatology when it lands).
_VARIABLE_MAP: dict[str, tuple[str, float]] = {
    "temperature": ("temp_anomaly_c", 0.0),
    "humidity": ("humidity_pct", 0.0),
    "wind": ("wind_speed_kmh", 0.0),
    "drought": ("drought_index", 0.0),
    # ponytail: current-hour precipitation, not a trailing accumulation — swap for a real
    # accumulation window when the flood model is calibrated against real labels.
    "precipitation": ("precipitation_mm", 0.0),
}


class WeatherEvent(GlobalEvent):
    """One weather measurement (a single variable) from a weather feed."""

    def to_observation(self) -> GlobalObservation:
        variable = self.payload["variable"]
        return GlobalObservation(
            cell_id=self.cell_id or assign_cell_id(self.location.lat, self.location.lon),
            variable=variable,
            value=float(self.payload["value"]),
            std=self.payload.get("std"),
            observed_at=self.observed_at,
            source=self.source,
        )


class WeatherAPIConnector(BaseAPIConnector):
    """Fetch a current-conditions reading from Open-Meteo and normalize it.

    Real by default (no key required). If the feed is unreachable it falls back to a
    deterministic synthetic reading, so ingestion runs with no network and never crashes.
    Pass ``base_url=None`` to force the offline reading (used in tests).
    """

    source = "weather_api"

    def __init__(
        self, *, location: GeoPoint | None = None, base_url: str | None = _OPEN_METEO_URL, **kwargs: Any
    ) -> None:
        super().__init__(base_url=base_url, **kwargs)
        self.location = location or GeoPoint(lat=37.0, lon=-120.0)  # California default

    def fetch(self) -> dict[str, Any]:
        if not self.base_url:
            self.last_data_source = "synthetic_fallback"
            return _offline_reading()
        try:
            raw = self.get_json(
                self.base_url,
                params={
                    "latitude": self.location.lat,
                    "longitude": self.location.lon,
                    "current": _OPEN_METEO_CURRENT,
                },
            )
        except ConnectorError as exc:
            self.last_data_source = "synthetic_fallback"
            logger.warning("[WARN] %s unreachable — serving offline synthetic reading: %s", self.source, exc)
            return _offline_reading()
        self.last_data_source = "live"
        return _parse_open_meteo(raw)

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


def _parse_open_meteo(raw: dict[str, Any]) -> dict[str, Any]:
    """Pull the ``current`` block from an Open-Meteo response into our flat reading shape.

    Tolerant of missing fields — a variable Open-Meteo omits is simply absent downstream.
    """
    current = raw.get("current") or {}
    reading: dict[str, Any] = {}
    temp = current.get("temperature_2m")
    humidity = current.get("relative_humidity_2m")
    wind = current.get("wind_speed_10m")
    precipitation = current.get("precipitation")
    if temp is not None:
        reading["temperature"] = float(temp)
    if wind is not None:
        reading["wind"] = float(wind)
    if humidity is not None:
        reading["humidity"] = float(humidity)
        reading["drought"] = _drought_from_humidity(float(humidity))
    if precipitation is not None:
        reading["precipitation"] = float(precipitation)
    return reading


def _drought_from_humidity(humidity_pct: float) -> float:
    """Derive a 0–1 drought index from relative humidity: drier air ⇒ higher drought.

    ponytail: a single-input proxy (dryness of the air) standing in for a real drought
    code — swap for a KBDI/precipitation-deficit index when a rainfall feed is wired in.
    """
    return round(min(1.0, max(0.0, 1.0 - humidity_pct / 100.0)), 3)


def _offline_reading() -> dict[str, Any]:
    """Deterministic clone-safe reading (hot, dry, breezy — a plausible fire day)."""
    return {
        "temperature": 34.0,
        "humidity": 20.0,
        "wind": 25.0,
        "drought": _drought_from_humidity(20.0),
        "precipitation": 0.0,
    }


def demo() -> None:
    """Self-check: an Open-Meteo payload normalizes to the four canonical observations."""
    raw = {
        "current": {
            "temperature_2m": 31.0,
            "relative_humidity_2m": 18.0,
            "wind_speed_10m": 22.0,
            "precipitation": 1.4,
        }
    }
    reading = _parse_open_meteo(raw)
    assert reading == {
        "temperature": 31.0, "wind": 22.0, "humidity": 18.0, "drought": 0.82, "precipitation": 1.4,
    }, reading
    obs = {e.to_observation().variable for e in WeatherAPIConnector(base_url=None).normalize(reading)}
    assert obs == {
        "temp_anomaly_c", "humidity_pct", "wind_speed_kmh", "drought_index", "precipitation_mm",
    }, obs
    print("OK", reading)


if __name__ == "__main__":
    demo()
