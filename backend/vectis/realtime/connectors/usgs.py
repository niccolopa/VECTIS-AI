"""USGS connector — real, worldwide earthquake detections into V3 events.

Reads the **keyless** USGS Earthquake Hazards GeoJSON summary feed and maps each feature to
a :class:`GlobalEvent` at its real ``(lat, lon)``, so quakes land on the H3 cell where they
actually struck.

**Feed choice — ``4.5_day`` (M4.5+, past 24 h).** The summary feeds trade window against
volume: ``all_day`` (M1+) is thousands of mostly-local micro-quakes, ``significant_*`` is a
handful. ``4.5_day`` is the sweet spot for a *global* hazard signal — every quake large
enough to matter anywhere on Earth, ~20–50/day, no micro-seismic noise. Override via the
``feed`` argument.

The feed needs **no API key**, so it's the connector where retry/backoff against a real
(mocked) transient failure is exercised most thoroughly — there's no credential logic in the
way. As with every connector, an outage degrades to deterministic offline quakes, never a crash.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from vectis.core.config import get_settings
from vectis.core.logging import get_logger
from vectis.realtime.connectors.base import BaseAPIConnector, ConnectorError
from vectis.realtime.events.base import GeoPoint, GlobalEvent, GlobalObservation
from vectis.realtime.state.cell_id import assign_cell_id

logger = get_logger(__name__)

_DEFAULT_FEED = "4.5_day"

# Deterministic global offline quakes (lat, lon, magnitude) on four continents — the
# network-free fallback, spread so degradation still exercises multiple cells/continents.
_OFFLINE_QUAKES: tuple[tuple[float, float, float], ...] = (
    (38.3, 142.4, 5.8),    # off Honshu, Japan
    (-33.4, -70.6, 5.2),   # central Chile
    (37.7, -122.0, 4.6),   # SF Bay Area, US
    (28.2, 84.7, 5.5),     # Nepal Himalaya
    (-6.2, 130.5, 5.0),    # Banda Sea, Indonesia
)


class QuakeEvent(GlobalEvent):
    """A single earthquake detection; magnitude carried in ``payload``."""

    def to_observation(self) -> GlobalObservation:
        return GlobalObservation(
            cell_id=self.cell_id or assign_cell_id(self.location.lat, self.location.lon),
            variable="earthquake_magnitude",
            value=float(self.payload["magnitude"]),
            observed_at=self.observed_at,
            source=self.source,
        )


class UsgsQuakeConnector(BaseAPIConnector):
    """Fetch the USGS earthquake summary feed and normalize it to events.

    Keyless and offline-safe: on any outage it serves deterministic global quakes so the
    hazard stream never stalls.
    """

    source = "usgs_quake"

    def __init__(
        self, *, feed: str = _DEFAULT_FEED, base_url: str | None = None, **kwargs: Any
    ) -> None:
        base = base_url if base_url is not None else get_settings().usgs_base_url
        super().__init__(base_url=base, **kwargs)
        self._feed = feed

    def fetch(self) -> dict[str, Any]:
        url = f"{self.base_url}/earthquakes/feed/v1.0/summary/{self._feed}.geojson"
        try:
            raw = self.get_json(url)
            self.last_data_source = "live"
            return raw
        except ConnectorError as exc:
            self.last_data_source = "synthetic_fallback"
            logger.warning("[WARN] %s unreachable — serving offline quakes: %s", self.source, exc)
            return {"features": [_offline_feature(*q) for q in _OFFLINE_QUAKES]}

    def normalize(self, raw: Any) -> list[GlobalEvent]:
        events: list[GlobalEvent] = []
        for feature in raw.get("features", []):
            coords = (feature.get("geometry") or {}).get("coordinates") or []
            if len(coords) < 2:
                continue  # a feature with no point is not placeable — skip, don't crash
            props = feature.get("properties") or {}
            mag = props.get("mag")
            if mag is None:
                continue
            events.append(
                QuakeEvent(
                    source=self.source,
                    location=GeoPoint(lat=float(coords[1]), lon=float(coords[0])),
                    confidence=_confidence(props),
                    observed_at=_quake_time(props.get("time")),
                    payload={
                        "magnitude": float(mag),
                        "depth_km": float(coords[2]) if len(coords) > 2 else None,
                        "place": props.get("place"),
                    },
                )
            )
        return events


def _confidence(props: dict[str, Any]) -> float:
    """Derive 0–1 confidence from the feed's magnitude uncertainty, when reported.

    Summary feeds usually omit ``magError``; when present, a larger error → lower confidence.
    Absent, default 1.0 (consistent with the GlobalEvent default).
    """
    mag_error = props.get("magError")
    if mag_error is None:
        return 1.0
    try:
        # ~0.0 error → 1.0; ~0.5 error → ~0.5; clamped to [0, 1].
        return max(0.0, min(1.0, 1.0 - float(mag_error)))
    except (TypeError, ValueError):
        return 1.0


def _quake_time(epoch_ms: Any) -> datetime:
    """USGS reports event time as epoch **milliseconds**; fall back to now if absent/bad."""
    try:
        return datetime.fromtimestamp(float(epoch_ms) / 1000.0, tz=UTC)
    except (TypeError, ValueError):
        return datetime.now(UTC)


def _offline_feature(lat: float, lon: float, mag: float) -> dict[str, Any]:
    """Shape an offline quake like a real USGS GeoJSON feature (lon, lat, depth)."""
    return {"geometry": {"coordinates": [lon, lat, 10.0]}, "properties": {"mag": mag}}


def demo() -> None:
    """Self-check: a GeoJSON feed normalizes to a quake at its real coordinate."""
    body = {
        "features": [
            {
                "geometry": {"coordinates": [142.4, 38.3, 24.0]},
                "properties": {"mag": 5.8, "time": 1_700_000_000_000, "place": "off Honshu"},
            }
        ]
    }
    obs = UsgsQuakeConnector(base_url="http://x").normalize(body)[0].to_observation()
    assert obs.variable == "earthquake_magnitude" and obs.value == 5.8
    assert obs.cell_id == assign_cell_id(38.3, 142.4)
    print("OK", obs.cell_id)


if __name__ == "__main__":
    demo()
