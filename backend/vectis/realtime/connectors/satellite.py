"""Satellite connector — NASA FIRMS active-fire detections into V3 events.

Reads the public **NASA FIRMS** active-fire feed (the open VIIRS/MODIS product) over the
area CSV API and turns each detection into a :class:`GlobalEvent` carrying a
``fire_radiative_power`` observation — a direct ignition signal for the wildfire model.

FIRMS gates the area API behind a free ``MAP_KEY``. It is read from
``VECTIS_FIRMS_API_KEY`` (via :class:`~vectis.core.config.Settings`); when it is absent
the connector serves deterministic offline detections, so a fresh clone runs with no key
and no network. The CSV is parsed with the stdlib ``csv`` module — no extra dependency.
"""

from __future__ import annotations

import csv
import io
from typing import Any

from vectis.core.config import get_settings
from vectis.core.logging import get_logger
from vectis.realtime.connectors.base import BaseAPIConnector
from vectis.realtime.events.base import GeoPoint, GlobalEvent, GlobalObservation
from vectis.realtime.state.cell_id import assign_cell_id

logger = get_logger(__name__)

# FIRMS confidence (0-100) → observation std: a low-confidence detection is noisier.
_MAX_FRP_STD = 50.0

# NASA FIRMS area CSV API. SOURCE picks the satellite product; AREA is a lon/lat bbox
# (west,south,east,north); DAY_RANGE is how many days back. California default bbox.
_FIRMS_BASE_URL = "https://firms.modaps.eosdis.nasa.gov"
_FIRMS_PRODUCT = "VIIRS_SNPP_NRT"
_FIRMS_AREA = "-122.0,36.0,-118.0,40.0"  # California, USA (W,S,E,N)
_FIRMS_DAY_RANGE = 1

# VIIRS reports confidence as a letter; MODIS as a 0-100 number. Map letters to a midpoint.
_CONFIDENCE_LETTERS = {"l": 30.0, "n": 70.0, "h": 95.0}


class FireDetectionEvent(GlobalEvent):
    """A single active-fire detection."""

    def to_observation(self) -> GlobalObservation:
        return GlobalObservation(
            cell_id=self.cell_id or assign_cell_id(self.location.lat, self.location.lon),
            variable="fire_radiative_power",
            value=float(self.payload["frp"]),
            std=self.payload.get("std"),
            observed_at=self.observed_at,
            source=self.source,
        )


class SatelliteAPIConnector(BaseAPIConnector):
    """Fetch NASA FIRMS active-fire detections for a region and normalize them.

    With a FIRMS ``MAP_KEY`` it calls the live area CSV API; without one it returns two
    deterministic offline detections so the ingestion layer runs key-free.
    """

    source = "nasa_firms"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        product: str = _FIRMS_PRODUCT,
        area: str = _FIRMS_AREA,
        day_range: int = _FIRMS_DAY_RANGE,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        # Explicit arg wins; otherwise read the env-backed setting (empty → offline).
        self._api_key = api_key if api_key is not None else get_settings().firms_api_key
        if not self._api_key:
            logger.warning(
                "[WARN] %s has no MAP_KEY (set VECTIS_FIRMS_API_KEY) — "
                "degrading to mocked California detections", self.source
            )
        self._product = product
        self._area = area
        self._day_range = day_range

    def fetch(self) -> Any:
        if not self._api_key:
            # No FIRMS key → deterministic offline detections (clone-safe, no network).
            return {
                "detections": [
                    {"latitude": 37.0, "longitude": -120.0, "frp": 12.4, "confidence": 80},
                    {"latitude": 37.3, "longitude": -119.6, "frp": 6.1, "confidence": 45},
                ]
            }
        url = (
            f"{self.base_url or _FIRMS_BASE_URL}/api/area/csv/"
            f"{self._api_key}/{self._product}/{self._area}/{self._day_range}"
        )
        return {"detections": _parse_firms_csv(self.get_text(url))}

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


def _parse_firms_csv(text: str) -> list[dict[str, Any]]:
    """Parse FIRMS area-CSV rows into the ``{latitude, longitude, frp, confidence}`` shape.

    Tolerant of the product differences: FRP may be missing on a row, and confidence is a
    0-100 number (MODIS) or an ``l``/``n``/``h`` letter (VIIRS). Bad rows are skipped, not
    fatal — a malformed line must not drop the whole batch.
    """
    detections: list[dict[str, Any]] = []
    for row in csv.DictReader(io.StringIO(text)):
        try:
            lat = float(row["latitude"])
            lon = float(row["longitude"])
        except (KeyError, TypeError, ValueError):
            continue
        detections.append(
            {
                "latitude": lat,
                "longitude": lon,
                "frp": _to_float(row.get("frp"), default=0.0),
                "confidence": _firms_confidence(row.get("confidence")),
            }
        )
    return detections


def _firms_confidence(raw: Any) -> float:
    """FIRMS confidence as a 0-100 number, mapping VIIRS letters to a midpoint."""
    if raw is None:
        return 50.0
    token = str(raw).strip().lower()
    if token in _CONFIDENCE_LETTERS:
        return _CONFIDENCE_LETTERS[token]
    return _to_float(token, default=50.0)


def _to_float(raw: Any, *, default: float) -> float:
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default
