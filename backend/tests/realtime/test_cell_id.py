"""Session 30 — H3 hierarchical cell addressing (replaces naive 0.1° quantization)."""

from __future__ import annotations

import h3

from vectis.realtime.state.cell_id import assign_cell_id, children_cell_ids, parent_cell_id


def test_assign_is_deterministic_and_at_default_resolution() -> None:
    cell = assign_cell_id(37.0, -120.0)
    assert cell == assign_cell_id(37.0, -120.0)  # same point → same cell
    assert h3.get_resolution(cell) == 5  # documented default


def test_nearby_points_share_a_cell_but_distant_ones_dont() -> None:
    # Perturbing a cell's own centroid by ~100 m stays inside the same ~8.5 km cell
    # (starting from the centroid avoids straddling a cell boundary).
    cell = assign_cell_id(37.0, -120.0)
    clat, clon = h3.cell_to_latlng(cell)
    assert assign_cell_id(clat + 0.001, clon + 0.001) == cell
    # Points hundreds of km apart must not share a cell.
    assert assign_cell_id(37.0, -120.0) != assign_cell_id(45.0, -90.0)


def test_parent_child_hierarchy_round_trips() -> None:
    cell = assign_cell_id(44.4, 8.9)  # resolution 5
    for child in children_cell_ids(cell, 7):
        assert h3.get_resolution(child) == 7
        assert parent_cell_id(child, 5) == cell  # every child rolls back up to its parent


def test_parent_is_coarser_and_stable() -> None:
    cell = assign_cell_id(-33.9, 151.2, resolution=6)  # Sydney, finer res
    parent = parent_cell_id(cell, 3)
    assert h3.get_resolution(parent) == 3
    # Adjacent fine cells fall under the same coarse parent — the aggregation guarantee.
    neighbor = assign_cell_id(-33.91, 151.21, resolution=6)
    assert parent_cell_id(neighbor, 3) == parent
