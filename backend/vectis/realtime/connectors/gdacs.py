"""GDACS connector — real, worldwide multi-hazard alerts into V3 events.

The Global Disaster Alert and Coordination System publishes one **keyless** feed carrying a
*mix* of hazard types — tropical cyclones, floods, tsunamis, volcanoes, earthquakes,
droughts, wildfires — each with an alert level (Green / Orange / Red) and a real location.

This connector deliberately emits that mix from one feed: Session-30's H3 grid and
Session-18's :class:`GlobalEvent` schema are hazard-agnostic, so there's no reason to force
GDACS into a fire-shaped payload. The **hazard type** rides in the event ``payload``/``metadata``
*and* — because :class:`GlobalObservation` has no free-form field — is preserved into the
observation through its **variable name** (``cyclone_alert_level``, ``flood_alert_level``, …),
so mixed hazards survive end to end into the state layer.

Keyless and offline-safe: any outage degrades to a deterministic set of global mixed-hazard
alerts, never a crash. Base URL from ``VECTIS_GDACS_BASE_URL`` (upstream or the Sluice).
"""

from __future__ import annotations

from typing import Any

from vectis.core.config import get_settings
from vectis.core.logging import get_logger
from vectis.realtime.connectors.base import BaseAPIConnector, ConnectorError
from vectis.realtime.events.base import GeoPoint, GlobalEvent, GlobalObservation
from vectis.realtime.state.cell_id import assign_cell_id

logger = get_logger(__name__)

_DEFAULT_PROFILE = "MAP"  # GDACS "current events" GeoJSON profile

# GDACS hazard codes → the canonical hazard name carried through the pipeline.
_HAZARD_TYPES: dict[str, str] = {
    "EQ": "earthquake",
    "TC": "cyclone",
    "FL": "flood",
    "VO": "volcano",
    "TS": "tsunami",
    "DR": "drought",
    "WF": "wildfire",
}
# Alert level → an ordinal severity the observation carries as its value.
_ALERT_LEVELS: dict[str, float] = {"green": 1.0, "orange": 2.0, "red": 3.0}

# Deterministic global mixed-hazard fallback (lat, lon, hazard_code, alert) — four hazard
# types on four continents, so degradation still spans multiple cells and hazard types.
_OFFLINE_ALERTS: tuple[tuple[float, float, str, str], ...] = (
    (14.6, 120.9, "TC", "Red"),      # cyclone, Philippines
    (23.8, 90.4, "FL", "Orange"),    # flood, Bangladesh
    (-0.8, -91.1, "VO", "Orange"),   # volcano, Galápagos
    (38.3, 142.4, "TS", "Red"),      # tsunami, off Japan
)


class GdacsAlertEvent(GlobalEvent):
    """A single GDACS multi-hazard alert; hazard type preserved into the observation variable."""

    def to_observation(self) -> GlobalObservation:
        hazard = self.payload.get("hazard", "hazard")
        return GlobalObservation(
            cell_id=self.cell_id or assign_cell_id(self.location.lat, self.location.lon),
            variable=f"{hazard}_alert_level",
            value=float(self.payload["alert_level"]),
            observed_at=self.observed_at,
            source=self.source,
        )


class GdacsConnector(BaseAPIConnector):
    """Fetch the GDACS multi-hazard alert feed and normalize it to mixed-hazard events."""

    source = "gdacs"

    def __init__(
        self, *, profile: str = _DEFAULT_PROFILE, base_url: str | None = None, **kwargs: Any
    ) -> None:
        base = base_url if base_url is not None else get_settings().gdacs_base_url
        super().__init__(base_url=base, **kwargs)
        self._profile = profile

    def fetch(self) -> dict[str, Any]:
        url = f"{self.base_url}/gdacsapi/api/events/geteventlist/{self._profile}"
        try:
            return self.get_json(url)
        except ConnectorError as exc:
            logger.warning("[WARN] %s unreachable — serving offline alerts: %s", self.source, exc)
            return {"features": [_offline_feature(*a) for a in _OFFLINE_ALERTS]}

    def normalize(self, raw: Any) -> list[GlobalEvent]:
        events: list[GlobalEvent] = []
        for feature in raw.get("features", []):
            coords = (feature.get("geometry") or {}).get("coordinates") or []
            if len(coords) < 2:
                continue  # unplaceable alert — skip, don't crash
            props = feature.get("properties") or {}
            hazard = _HAZARD_TYPES.get(str(props.get("eventtype", "")).upper(), "hazard")
            alert = _ALERT_LEVELS.get(str(props.get("alertlevel", "")).strip().lower(), 1.0)
            events.append(
                GdacsAlertEvent(
                    source=self.source,
                    location=GeoPoint(lat=float(coords[1]), lon=float(coords[0])),
                    payload={
                        "hazard": hazard,
                        "alert_level": alert,
                        "alert": props.get("alertlevel"),
                        "name": props.get("eventname") or props.get("name"),
                        "country": props.get("country"),
                    },
                    metadata={"eventtype": props.get("eventtype"), "eventid": props.get("eventid")},
                )
            )
        return events


def _offline_feature(lat: float, lon: float, code: str, alert: str) -> dict[str, Any]:
    return {
        "geometry": {"coordinates": [lon, lat]},
        "properties": {"eventtype": code, "alertlevel": alert},
    }


def demo() -> None:
    """Self-check: mixed hazard codes survive into distinct observation variables."""
    conn = GdacsConnector(base_url="http://x")
    raw = {"features": [_offline_feature(*a) for a in _OFFLINE_ALERTS]}
    variables = {e.to_observation().variable for e in conn.normalize(raw)}
    assert {"cyclone_alert_level", "flood_alert_level", "volcano_alert_level", "tsunami_alert_level"} <= variables
    print("OK", sorted(variables))


if __name__ == "__main__":
    demo()
