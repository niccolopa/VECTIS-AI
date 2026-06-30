"""Region registry.

A region defines the geographic extent and grid resolution of an analysis.
California (USA) is the bundled demo region; adding a region is a matter of
adding an entry here and providing data (sample or via a live connector).
"""

from __future__ import annotations

from dataclasses import dataclass

from vectis.core.exceptions import RegionNotFoundError


@dataclass(frozen=True)
class BBox:
    """Geographic bounding box in WGS84 degrees."""

    min_lat: float
    min_lon: float
    max_lat: float
    max_lon: float


@dataclass(frozen=True)
class Region:
    """A named area of analysis with a regular lat/lon grid."""

    key: str
    label: str
    country: str
    bbox: BBox
    rows: int  # grid cells along latitude
    cols: int  # grid cells along longitude

    @property
    def n_cells(self) -> int:
        return self.rows * self.cols


# California: the wildfire-prone US West Coast state — a globally recognized
# climate-risk theatre. The bundled demo region: changing this bbox is what
# migrates the generated sample grid onto North America so it plots there.
CALIFORNIA = Region(
    key="california",
    label="California, USA",
    country="US",
    bbox=BBox(min_lat=36.0, min_lon=-122.0, max_lat=40.0, max_lon=-118.0),
    rows=12,
    cols=20,
)

# Additional globally recognizable wildfire regions (live-twin / catalog entries).
NEW_SOUTH_WALES = Region(
    key="new_south_wales",
    label="New South Wales, Australia",
    country="AU",
    bbox=BBox(min_lat=-34.5, min_lon=149.0, max_lat=-32.5, max_lon=151.5),
    rows=12,
    cols=20,
)

ATTICA = Region(
    key="attica",
    label="Attica, Greece",
    country="GR",
    bbox=BBox(min_lat=37.8, min_lon=23.4, max_lat=38.4, max_lon=24.1),
    rows=12,
    cols=20,
)

REGIONS: dict[str, Region] = {r.key: r for r in (CALIFORNIA, NEW_SOUTH_WALES, ATTICA)}


def get_region(key: str) -> Region:
    """Look up a region by key, raising :class:`RegionNotFoundError` if absent."""
    try:
        return REGIONS[key.lower()]
    except KeyError as exc:
        known = ", ".join(sorted(REGIONS))
        raise RegionNotFoundError(f"Unknown region '{key}'. Known regions: {known}.") from exc
