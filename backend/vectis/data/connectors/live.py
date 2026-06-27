"""Live connector stubs (opt-in).

These document the integration surface for real Earth-observation sources and
implement the :class:`Connector` interface. They intentionally raise until
configured with credentials — wiring them up is a roadmap item, and doing so
must not break VECTIS's offline-by-default reproducibility guarantee.

To implement one: fetch the source for ``region.bbox`` over the window, map its
fields onto ``vectis.data.pipeline.schema.RAW_COLUMNS`` at the region's grid
resolution, and return a :class:`RawFrame`.
"""

from __future__ import annotations

from vectis.core.exceptions import VectisError
from vectis.data.connectors.base import Connector, RawFrame
from vectis.data.regions import Region


class _NotConfigured(Connector):
    provider = "live"
    docs = ""

    def fetch(self, region: Region, window_days: int = 30) -> RawFrame:  # noqa: ARG002
        raise VectisError(
            f"The '{self.provider}' connector is not configured. It requires "
            f"credentials and the optional 'live' extras (`pip install -e '.[live]'`). "
            f"See {self.docs}. Use the default 'sample' connector for offline runs."
        )


class FirmsConnector(_NotConfigured):
    """NASA FIRMS — active fire / thermal anomaly detections (MODIS/VIIRS)."""

    name = "firms"
    provider = "NASA FIRMS"
    docs = "https://firms.modaps.eosdis.nasa.gov/api/"


class Era5Connector(_NotConfigured):
    """Copernicus ERA5 reanalysis — temperature, humidity, wind."""

    name = "era5"
    provider = "Copernicus ERA5"
    docs = "https://cds.climate.copernicus.eu/"


class CopernicusLandConnector(_NotConfigured):
    """Copernicus Land Monitoring — NDVI / vegetation and land cover."""

    name = "copernicus"
    provider = "Copernicus Land"
    docs = "https://land.copernicus.eu/"


_LIVE: dict[str, type[_NotConfigured]] = {
    c.name: c for c in (FirmsConnector, Era5Connector, CopernicusLandConnector)
}


def get_live_connector(name: str) -> Connector:
    try:
        return _LIVE[name]()
    except KeyError as exc:
        known = ", ".join(["sample", *_LIVE])
        raise VectisError(f"Unknown connector '{name}'. Available: {known}.") from exc
