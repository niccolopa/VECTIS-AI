"""Historical NASA FIRMS active-fire detections — the calibration *labels*.

Reads the same FIRMS area-CSV API the Session-31 live connector uses, but pointed at a
**standard-processing archive product** (``VIIRS_SNPP_SP``) over an explicit historical
window instead of the near-real-time feed. Each returned detection is a confirmed
active-fire observation at a real ``(lat, lon, timestamp)`` — a positive fire-occurrence
label for the spatial-temporal join in :mod:`vectis.calibration.data.dataset`.

API shape (chunking): ``/api/area/csv/{MAP_KEY}/{product}/{west},{south},{east},{north}/
{day_range}/{start_date}`` — FIRMS caps ``day_range`` at 10, so a long window is fetched
as consecutive ≤10-day chunks. CSV parsing reuses the live connector's tolerant
``_parse_firms_csv`` (one parser, two call sites).

Credentials: a free MAP_KEY (``VECTIS_FIRMS_API_KEY``), from
https://firms.modaps.eosdis.nasa.gov/api/map_key/ — or a Sluice gateway base URL that
holds the key. With neither, :meth:`FirmsArchiveClient.fetch_detections` raises
:class:`CalibrationDataError`: **no offline fallback here** — fabricated labels would
poison the fit.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from vectis.calibration.data.base import ArchiveHttp, CalibrationDataError
from vectis.core.config import get_settings
from vectis.core.logging import get_logger
from vectis.data.regions import BBox
from vectis.realtime.connectors.firms import _FIRMS_UPSTREAM, _parse_firms_csv

logger = get_logger(__name__)

#: Standard-processing (science-quality) VIIRS product — the historical archive. The
#: ``_NRT`` variant only covers the last ~2 months; ``_SP`` is the calibration source.
ARCHIVE_PRODUCT = "VIIRS_SNPP_SP"

#: FIRMS area API hard limit on days per request.
_MAX_DAY_RANGE = 10


class FirmsArchiveClient:
    """Fetch historical FIRMS detections for a bbox + date window, chunked and parsed."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        product: str = ARCHIVE_PRODUCT,
        **http_kwargs: Any,
    ) -> None:
        settings = get_settings()
        self._api_key = api_key if api_key is not None else settings.firms_api_key
        self._base_url = (base_url if base_url is not None else settings.firms_base_url).rstrip("/")
        self._product = product
        self._http = ArchiveHttp(base_url=self._base_url, **http_kwargs)
        # Same rule as the live connector: a non-upstream base means a gateway holds the key.
        self._via_gateway = self._base_url != _FIRMS_UPSTREAM

    def fetch_detections(
        self, bbox: BBox, start: date, end: date
    ) -> list[dict[str, Any]]:
        """All archive detections inside ``bbox`` between ``start`` and ``end`` (inclusive).

        Returns the live parser's row dicts: ``latitude``, ``longitude``, ``frp``,
        ``confidence`` (0–100), ``observed_at`` (UTC datetime or ``None``).
        """
        if end < start:
            raise ValueError(f"end {end} precedes start {start}")
        if not self._api_key and not self._via_gateway:
            raise CalibrationDataError(
                "FIRMS archive access needs a MAP_KEY: set VECTIS_FIRMS_API_KEY (free at "
                "https://firms.modaps.eosdis.nasa.gov/api/map_key/) or point "
                "VECTIS_FIRMS_BASE_URL at a Sluice gateway that holds one. Calibration "
                "never substitutes synthetic labels."
            )
        key = self._api_key or "MANAGED"  # gateway holds the real key (path-shape parity)
        area = f"{bbox.min_lon},{bbox.min_lat},{bbox.max_lon},{bbox.max_lat}"  # W,S,E,N

        detections: list[dict[str, Any]] = []
        chunk_start = start
        while chunk_start <= end:
            days = min(_MAX_DAY_RANGE, (end - chunk_start).days + 1)
            url = (
                f"{self._base_url}/api/area/csv/{key}/{self._product}/"
                f"{area}/{days}/{chunk_start.isoformat()}"
            )
            detections.extend(_parse_firms_csv(self._http.get_text(url)))
            chunk_start += timedelta(days=days)
        logger.info(
            "[INFO] FIRMS archive: %d detections in %s over %s..%s",
            len(detections), area, start, end,
        )
        return detections
