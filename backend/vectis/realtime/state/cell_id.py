"""H3 hierarchical cell addressing — the global grid's coordinate system.

Session 30 retires ``naive_cell_id``'s flat 0.1° lat/lon quantization (a Session-17/18
placeholder) for **Uber H3**: a hexagonal, globally-consistent, *hierarchical* grid. Two
properties are why V4 needs it over a rectangular raster:

- **Equal-ish area cells.** A 0.1° box is ~11 km at the equator but collapses toward the
  poles; H3 hexagons stay far closer to constant area everywhere, so "one cell" means the
  same thing in California and in Siberia.
- **Hierarchy.** Every cell has exactly one parent at each coarser resolution and a fixed
  set of children at each finer one. That is the precondition for the tiling / zoom /
  aggregation the rest of the V4 arc (Session 31+ ingestion, later tile server) stands on.

**Default resolution 5 (~8.5 km edge, ~252 km² per cell).** Chosen as the wildfire sweet
spot: fine enough that one cell is a meaningful fire-behaviour unit (a single H3-5 cell is
roughly a large fire's active footprint), coarse enough that the *global active set* stays
small — the whole planet is only ~2M H3-5 cells, and we only ever materialize the handful
that have live data. Finer (res 6–7) would multiply the active set for no modelling gain
at wildfire scale; coarser (res 3–4) would smear distinct fires into one cell.
"""

from __future__ import annotations

import h3

from vectis.realtime.events.base import CellId

#: Default H3 resolution for observation addressing (~8.5 km edge). See module docstring.
DEFAULT_RESOLUTION = 5


def assign_cell_id(lat: float, lon: float, resolution: int = DEFAULT_RESOLUTION) -> CellId:
    """Map a coordinate to the H3 cell index containing it (the V4 replacement for
    ``naive_cell_id``). Returns the H3 index as a hex string — an opaque, shardable
    :data:`CellId` the rest of the pipeline already treats as a black box."""
    return h3.latlng_to_cell(lat, lon, resolution)


def parent_cell_id(cell_id: CellId, parent_resolution: int) -> CellId:
    """The single coarser-resolution cell that contains ``cell_id``.

    ``parent_resolution`` must be ≤ the cell's own resolution (a parent is coarser).
    Unused today (no tile server yet) but the aggregation primitive Session 31+ needs.
    """
    return h3.cell_to_parent(cell_id, parent_resolution)


def children_cell_ids(cell_id: CellId, child_resolution: int) -> list[CellId]:
    """The finer-resolution cells that tile ``cell_id``.

    ``child_resolution`` must be ≥ the cell's own resolution. The inverse of
    :func:`parent_cell_id`; every child's parent at this cell's resolution is ``cell_id``.
    """
    return h3.cell_to_children(cell_id, child_resolution)


def demo() -> None:
    """Self-check: addressing is stable and the hierarchy round-trips."""
    # Same point → same cell; nearby points within ~8.5 km → same res-5 cell.
    c = assign_cell_id(37.0, -120.0)
    assert c == assign_cell_id(37.0, -120.0)
    assert h3.get_resolution(c) == 5

    # A child's parent at the original resolution is the original cell (round-trip).
    child = children_cell_ids(c, 7)[0]
    assert parent_cell_id(child, 5) == c
    print("OK", c)


if __name__ == "__main__":
    demo()
