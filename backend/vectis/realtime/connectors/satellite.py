"""Satellite connector — active-fire detections (NASA FIRMS style) into V3 events.

Mimics the FIRMS active-fire feed: a list of detections, each with a coordinate, a
brightness/fire-radiative-power reading, and a confidence. Each detection becomes one
:class:`GlobalEvent` carrying a ``fire_radiative_power`` observation — a direct
ignition signal for the wildfire model.
"""

from __future__ import annotations

from typing import Any

from vectis.realtime.connectors.base import BaseAPIConnector
from vectis.realtime.events.base import GeoPoint, GlobalEvent, GlobalObservation, naive_cell_id

# FIRMS confidence (0-100) → observation std: a low-confidence detection is noisier.
_MAX_FRP_STD = 50.0


class FireDetectionEvent(GlobalEvent):
    """A single active-fire detection."""

    def to_observation(self) -> GlobalObservation:
        return GlobalObservation(
            cell_id=self.cell_id or naive_cell_id(self.location),
            variable="fire_radiative_power",
            value=float(self.payload["frp"]),
            std=self.payload.get("std"),
            observed_at=self.observed_at,
            source=self.source,
        )


class SatelliteAPIConnector(BaseAPIConnector):
    """Fetch active-fire detections for a region and normalize them.

    Offline-safe: with no ``base_url`` it returns two deterministic detections.
    """

    source = "nasa_firms"

    def fetch(self) -> Any:
        if not self.base_url:
            return {
                "detections": [
                    {"latitude": 44.41, "longitude": 8.93, "frp": 12.4, "confidence": 80},
                    {"latitude": 44.10, "longitude": 9.84, "frp": 6.1, "confidence": 45},
                ]
            }
        return self.get_json(f"{self.base_url}/active_fire")

    def normalize(self, raw: Any) -> list[GlobalEvent]:
        events: list[GlobalEvent] = []
        for det in raw.get("detections", []):
            confidence = max(0.0, min(float(det.get("confidence", 50)), 100.0))
            # Lower confidence → larger measurement uncertainty.
            std = _MAX_FRP_STD * (1.0 - confidence / 100.0)
            events.append(
                FireDetectionEvent(
                    source=self.source,
                    location=GeoPoint(lat=float(det["latitude"]), lon=float(det["longitude"])),
                    confidence=confidence / 100.0,
                    payload={"frp": float(det["frp"]), "std": std},
                )
            )
        return events
