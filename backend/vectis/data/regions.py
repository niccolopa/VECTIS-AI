"""Region registry.

A region defines the geographic extent and grid resolution of an analysis.
Liguria (Italy) is the bundled demo region; adding a region is a matter of
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


# Liguria: the arc of north-west Italy along the Mediterranean — a region with a
# real, well-documented summer wildfire profile, which makes it a meaningful
# demo for climate-risk intelligence.
LIGURIA = Region(
    key="liguria",
    label="Liguria, Italy",
    country="IT",
    bbox=BBox(min_lat=43.78, min_lon=7.49, max_lat=44.68, max_lon=10.07),
    rows=12,
    cols=20,
)

REGIONS: dict[str, Region] = {LIGURIA.key: LIGURIA}


def get_region(key: str) -> Region:
    """Look up a region by key, raising :class:`RegionNotFoundError` if absent."""
    try:
        return REGIONS[key.lower()]
    except KeyError as exc:
        known = ", ".join(sorted(REGIONS))
        raise RegionNotFoundError(f"Unknown region '{key}'. Known regions: {known}.") from exc
