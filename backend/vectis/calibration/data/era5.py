"""Historical ERA5 reanalysis weather — the calibration *features*.

Fetches hourly ERA5 (temperature, relative humidity, wind, precipitation) for explicit
points and windows via **Open-Meteo's keyless historical archive API** (``/v1/era5``,
which serves the Copernicus ERA5 dataset) and aggregates it to the fire-weather daily
summary the join consumes: daily max temperature, min relative humidity, max wind, and
precipitation sum. Daily *max/min* rather than means because fire risk is driven by the
worst hour of the day, not the average one.

Why Open-Meteo and not the CDS API directly: same ERA5 data, zero credentials, JSON per
point instead of a queued NetCDF download — consistent with the Session-29 live-weather
choice, and it keeps the whole calibration pipeline down to one credential (FIRMS). The
``cdsapi`` route (already in the ``live`` extra; would use ``VECTIS_CDS_API_KEY``) only
pays off for bulk gridded pulls far beyond this per-cell join. ERA5 publishes with a
~5-day lag, so ``end`` must be at least a few days in the past.

No offline fallback — see :mod:`vectis.calibration.data.base`.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, NamedTuple

from vectis.calibration.data.base import ArchiveHttp
from vectis.core.config import get_settings
from vectis.core.logging import get_logger

logger = get_logger(__name__)

#: Hourly ERA5 variables requested — Open-Meteo defaults are already the project's
#: canonical units (°C, %, km/h, mm), so no conversion happens anywhere downstream.
_HOURLY_VARS = "temperature_2m,relative_humidity_2m,wind_speed_10m,precipitation"

#: Locations per request. Open-Meteo accepts comma-separated coordinate lists; batching
#: keeps a 500-cell region to ~10 requests instead of 500.
_BATCH_SIZE = 50


class DailyWeather(NamedTuple):
    """One place-day of fire-relevant ERA5 aggregates."""

    day: date
    temp_max_c: float
    rh_min_pct: float
    wind_max_kmh: float
    precip_mm: float


class Era5Client:
    """Fetch ERA5 hourly history for a set of points and reduce it to daily summaries."""

    def __init__(self, *, base_url: str | None = None, **http_kwargs: Any) -> None:
        base = base_url if base_url is not None else get_settings().era5_base_url
        self._base_url = base.rstrip("/")
        self._http = ArchiveHttp(base_url=self._base_url, **http_kwargs)

    def fetch_daily(
        self, points: list[tuple[float, float]], start: date, end: date
    ) -> list[list[DailyWeather]]:
        """Daily summaries per point (result aligned index-for-index with ``points``)."""
        if end < start:
            raise ValueError(f"end {end} precedes start {start}")
        results: list[list[DailyWeather]] = []
        for offset in range(0, len(points), _BATCH_SIZE):
            batch = points[offset : offset + _BATCH_SIZE]
            payload = self._http.get_json(
                f"{self._base_url}/v1/era5",
                params={
                    "latitude": ",".join(f"{lat:.4f}" for lat, _ in batch),
                    "longitude": ",".join(f"{lon:.4f}" for _, lon in batch),
                    "start_date": start.isoformat(),
                    "end_date": end.isoformat(),
                    "hourly": _HOURLY_VARS,
                    "timezone": "UTC",
                },
            )
            # One location comes back as a dict, several as a list — normalize to a list.
            locations = payload if isinstance(payload, list) else [payload]
            if len(locations) != len(batch):
                raise ValueError(
                    f"ERA5 archive returned {len(locations)} locations for {len(batch)} requested"
                )
            results.extend(_aggregate_daily(loc.get("hourly", {})) for loc in locations)
        logger.info(
            "[INFO] ERA5 archive: %d points over %s..%s aggregated to daily", len(points), start, end
        )
        return results


def _aggregate_daily(hourly: dict[str, list[Any]]) -> list[DailyWeather]:
    """Reduce one location's hourly arrays to per-day aggregates, skipping data gaps."""
    times = hourly.get("time", [])
    temp = hourly.get("temperature_2m", [])
    rh = hourly.get("relative_humidity_2m", [])
    wind = hourly.get("wind_speed_10m", [])
    precip = hourly.get("precipitation", [])

    by_day: dict[date, dict[str, list[float]]] = {}
    for i, stamp in enumerate(times):
        day = datetime.fromisoformat(stamp).date()
        bucket = by_day.setdefault(day, {"temp": [], "rh": [], "wind": [], "precip": []})
        for key, series in (("temp", temp), ("rh", rh), ("wind", wind), ("precip", precip)):
            value = series[i] if i < len(series) else None
            if value is not None:  # ERA5 gaps arrive as nulls — skip, never invent
                bucket[key].append(float(value))

    return [
        DailyWeather(
            day=day,
            temp_max_c=max(v["temp"]),
            rh_min_pct=min(v["rh"]) if v["rh"] else 50.0,
            wind_max_kmh=max(v["wind"]) if v["wind"] else 0.0,
            precip_mm=sum(v["precip"]),
        )
        for day, v in sorted(by_day.items())
        if v["temp"]  # a day with no temperature at all is a hole, not a zero
    ]
