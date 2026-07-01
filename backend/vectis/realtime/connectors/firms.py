"""FIRMS connector — real, worldwide active-fire detections into V3 events.

The Session-31 replacement for the California-pinned ``SatelliteAPIConnector``. It reads
the public **NASA FIRMS** active-fire feed over the *global* area CSV API and turns each
detection row into a :class:`GlobalEvent` at its **real ``(lat, lon)``** — a fire in
California and a fire in Australia land on different H3 cells, as they must.

Credential + endpoint:

- The MAP_KEY is read from ``VECTIS_FIRMS_API_KEY``. The base URL is ``VECTIS_FIRMS_BASE_URL``
  — the real upstream by default, or the optional :mod:`vectis.ingress.sluice` gateway. When
  the Sluice is the target it holds the credential, so this connector needs no key of its own.
- **Graceful degradation (mandatory, tested):** with no key *and* no Sluice, or on any feed
  failure, ``collect()`` never raises — it logs once and serves a small set of deterministic
  synthetic detections spread across the globe, exactly like every other connector here.

The CSV is parsed with the stdlib ``csv`` module — no extra dependency. Confidence routing
reuses the Session-18 pattern: FIRMS confidence (0–100, or VIIRS ``l``/``n``/``h``) becomes
the event ``confidence`` and drives the observation ``std`` (a low-confidence hit is noisier).
"""

from __future__ import annotations

import csv
import io
from datetime import UTC, datetime
from typing import Any

from vectis.core.config import get_settings
from vectis.core.logging import get_logger
from vectis.realtime.connectors.base import BaseAPIConnector, ConnectorError
from vectis.realtime.events.base import GeoPoint, GlobalEvent, GlobalObservation
from vectis.realtime.state.cell_id import assign_cell_id

logger = get_logger(__name__)

# The real FIRMS host. If the configured base URL differs from this, a Sluice (or another
# override) is in play — which holds the credential, so we can go live without our own key.
_FIRMS_UPSTREAM = "https://firms.modaps.eosdis.nasa.gov"
_FIRMS_PRODUCT = "VIIRS_SNPP_NRT"
_FIRMS_AREA_WORLD = "-180,-90,180,90"  # global bbox (W,S,E,N) — the whole planet
_FIRMS_DAY_RANGE = 1

# FIRMS confidence (0-100) → observation std: a low-confidence detection is noisier.
_MAX_FRP_STD = 50.0
# VIIRS reports confidence as a letter; MODIS as a 0-100 number. Map letters to a midpoint.
_CONFIDENCE_LETTERS = {"l": 30.0, "n": 70.0, "h": 95.0}

# A handful of real-world fire regions on four continents — the offline fallback. Spread
# on purpose so degradation still exercises multiple H3 cells / continents, not one point.
_OFFLINE_DETECTIONS: tuple[tuple[float, float, float, float], ...] = (
    (37.0, -120.0, 14.2, 80.0),    # California, US
    (-9.5, -62.0, 21.0, 72.0),     # Rondônia, BR
    (-33.4, 150.3, 18.5, 65.0),    # New South Wales, AU
    (38.5, 23.6, 9.8, 55.0),       # Attica, GR
    (0.5, 24.0, 12.1, 60.0),       # Congo Basin
)


class FireDetectionEvent(GlobalEvent):
    """A single active-fire detection at a real coordinate."""

    def to_observation(self) -> GlobalObservation:
        return GlobalObservation(
            cell_id=self.cell_id or assign_cell_id(self.location.lat, self.location.lon),
            variable="fire_radiative_power",
            value=float(self.payload["frp"]),
            std=self.payload.get("std"),
            observed_at=self.observed_at,
            source=self.source,
        )


class FirmsConnector(BaseAPIConnector):
    """Fetch worldwide NASA FIRMS active-fire detections and normalize them to events.

    Live when a MAP_KEY is set or a Sluice base URL is configured; otherwise (and on any
    outage) it degrades to deterministic global offline detections, so the fire feed runs
    key-free and network-free without ever crashing the ingestion sweep.
    """

    source = "nasa_firms"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        product: str = _FIRMS_PRODUCT,
        area: str = _FIRMS_AREA_WORLD,
        day_range: int = _FIRMS_DAY_RANGE,
        **kwargs: Any,
    ) -> None:
        settings = get_settings()
        base = base_url if base_url is not None else settings.firms_base_url
        super().__init__(base_url=base, **kwargs)
        self._api_key = api_key if api_key is not None else settings.firms_api_key
        # A base that isn't the real FIRMS host means a Sluice/override holds the key for us.
        self._via_gateway = (base or "").rstrip("/") != _FIRMS_UPSTREAM
        self._live = bool(self._api_key) or self._via_gateway
        if not self._live:
            logger.warning(
                "[WARN] %s has no MAP_KEY (set VECTIS_FIRMS_API_KEY) and no gateway — "
                "degrading to deterministic global offline detections", self.source
            )
        self._product = product
        self._area = area
        self._day_range = day_range

    def fetch(self) -> dict[str, Any]:
        if not self._live:
            return {"detections": _offline_detections()}
        # When a gateway holds the key, send a placeholder segment for path-shape parity.
        key = self._api_key or "MANAGED"
        url = (
            f"{self.base_url}/api/area/csv/{key}/{self._product}/{self._area}/{self._day_range}"
        )
        try:
            return {"detections": _parse_firms_csv(self.get_text(url))}
        except ConnectorError as exc:
            logger.warning("[WARN] %s unreachable — serving offline detections: %s", self.source, exc)
            return {"detections": _offline_detections()}

    def normalize(self, raw: Any) -> list[GlobalEvent]:
        events: list[GlobalEvent] = []
        for det in raw.get("detections", []):
            confidence = max(0.0, min(float(det.get("confidence", 50)), 100.0))
            std = _MAX_FRP_STD * (1.0 - confidence / 100.0)  # lower confidence → larger σ
            observed_at = det.get("observed_at")
            events.append(
                FireDetectionEvent(
                    source=self.source,
                    location=GeoPoint(lat=float(det["latitude"]), lon=float(det["longitude"])),
                    confidence=confidence / 100.0,
                    observed_at=observed_at or datetime.now(UTC),
                    payload={"frp": float(det["frp"]), "std": std},
                )
            )
        return events


def _offline_detections() -> list[dict[str, Any]]:
    return [
        {"latitude": lat, "longitude": lon, "frp": frp, "confidence": conf}
        for lat, lon, frp, conf in _OFFLINE_DETECTIONS
    ]


def _parse_firms_csv(text: str) -> list[dict[str, Any]]:
    """Parse FIRMS area-CSV rows into ``{latitude, longitude, frp, confidence, observed_at}``.

    Tolerant of product differences: FRP may be missing, confidence is a 0-100 number (MODIS)
    or an ``l``/``n``/``h`` letter (VIIRS), and the acquisition time may be malformed. A bad
    row is skipped, never fatal — one broken line must not drop the whole batch.
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
                "observed_at": _firms_observed_at(row.get("acq_date"), row.get("acq_time")),
            }
        )
    return detections


def _firms_observed_at(acq_date: Any, acq_time: Any) -> datetime | None:
    """Combine FIRMS ``acq_date`` (YYYY-MM-DD) + ``acq_time`` (HHMM, sometimes un-padded)."""
    if not acq_date:
        return None
    try:
        hhmm = str(acq_time or "0").strip().zfill(4)
        return datetime.strptime(f"{acq_date} {hhmm}", "%Y-%m-%d %H%M").replace(tzinfo=UTC)
    except (ValueError, TypeError):
        return None


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


def demo() -> None:
    """Self-check: no key + no gateway → global offline detections on distinct H3 cells."""
    conn = FirmsConnector(api_key="", base_url=_FIRMS_UPSTREAM, sleep=lambda _: None)
    obs = [e.to_observation() for e in conn.collect()]
    assert len(obs) == len(_OFFLINE_DETECTIONS)
    assert len({o.cell_id for o in obs}) == len(obs), "offline fires must span distinct cells"
    print("OK", len(obs), "global fire detections")


if __name__ == "__main__":
    demo()
