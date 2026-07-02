"""Session 36 — the tile server: zoom mapping, screening-only sourcing, aggregation."""

from __future__ import annotations

import ast
from pathlib import Path

from vectis.api.routers import tiles
from vectis.api.routers.tiles import TileCache, build_tile, h3_resolution_for_zoom, serve_tile
from vectis.realtime.state.cell_id import assign_cell_id, children_cell_ids, parent_cell_id
from vectis.realtime.state.models import WorldCellState

# Two well-separated California points that land on distinct res-5 cells.
_HOT = (37.0, -120.0)
_MILD = (39.5, -121.5)


def _hot_cell() -> WorldCellState:
    return WorldCellState(
        cell_id=assign_cell_id(*_HOT),
        temperature=40.0,
        flood_alert_level=3.0,
        precipitation_mm=95.0,
        extra={"wind_speed_kmh": 60.0},
    )


def _mild_cell() -> WorldCellState:
    return WorldCellState(cell_id=assign_cell_id(*_MILD), temperature=12.0)


# ── the documented zoom → H3 resolution mapping ─────────────────────────────────────────
def test_zoom_to_resolution_mapping_matches_the_documented_table() -> None:
    expected = {0: 2, 2: 2, 3: 3, 4: 3, 5: 4, 6: 4, 7: 5, 8: 5, 9: 6, 10: 6, 11: 7, 15: 7, 22: 7}
    assert {z: h3_resolution_for_zoom(z) for z in expected} == expected


# ── the endpoint ────────────────────────────────────────────────────────────────────────
def test_tiles_endpoint_serves_screened_cells_in_the_viewport(client) -> None:
    client.app.state.tile_store.save_state(_hot_cell())
    client.app.state.tile_store.save_state(_mild_cell())

    res = client.get(
        "/api/v1/tiles",
        params={"west": -125, "south": 32, "east": -114, "north": 42, "zoom": 8},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["resolution"] == 5  # zoom 8 → the native grid resolution
    by_id = {c["cell_id"]: c for c in body["cells"]}
    hot, mild = by_id[assign_cell_id(*_HOT)], by_id[assign_cell_id(*_MILD)]
    assert hot["hazards"]["wildfire"] > mild["hazards"]["wildfire"]
    assert hot["hazards"]["flood"] > 50.0  # red alert + heavy rain screens high
    assert "flood" not in mild["hazards"]  # no flood state → no fabricated score


def test_tiles_endpoint_respects_the_viewport_bbox(client) -> None:
    client.app.state.tile_store.save_state(_hot_cell())
    res = client.get(
        "/api/v1/tiles",
        params={"west": 10, "south": 40, "east": 20, "north": 50, "zoom": 8},  # Europe
    )
    assert res.status_code == 200
    assert res.json()["cells"] == []  # the California cell is outside the viewport


def test_tiles_endpoint_filters_to_one_hazard(client) -> None:
    client.app.state.tile_store.save_state(_hot_cell())
    res = client.get(
        "/api/v1/tiles",
        params={"west": -125, "south": 32, "east": -114, "north": 42, "zoom": 8,
                "hazard": "flood"},
    )
    cells = res.json()["cells"]
    assert cells and all(set(c["hazards"]) == {"flood"} for c in cells)


def test_tiles_endpoint_refuses_unscreened_and_unknown_hazards(client) -> None:
    params = {"west": -125, "south": 32, "east": -114, "north": 42, "zoom": 8}
    unscreened = client.get("/api/v1/tiles", params={**params, "hazard": "tsunami"})
    assert unscreened.status_code == 404
    assert "no screening model" in unscreened.json()["detail"]  # honest, not a fake zero
    unknown = client.get("/api/v1/tiles", params={**params, "hazard": "sharknado"})
    assert unknown.status_code == 404
    assert "unknown hazard" in unknown.json()["detail"]


def test_fine_resolutions_subdivide_without_fabricating_precision(client) -> None:
    client.app.state.tile_store.save_state(_hot_cell())
    res = client.get(
        "/api/v1/tiles",
        params={"west": -125, "south": 32, "east": -114, "north": 42, "zoom": 10},
    )
    body = res.json()
    assert body["resolution"] == 6
    # One native cell → 7 res-6 children, every child inheriting the parent's exact score.
    assert len(body["cells"]) == 7
    assert len({c["hazards"]["wildfire"] for c in body["cells"]}) == 1


# ── the structural guarantee: tiles never touch the expensive tiers ─────────────────────
def test_tile_router_never_imports_the_simulation_engine_or_the_pipeline() -> None:
    # Tiles are a view of the Tier-0 screen. Rendering a map must never be able to
    # trigger T1 (Monte Carlo) or T2 (board) work — proven on imports, not asserted in prose.
    assert tiles.__file__ is not None
    tree = ast.parse(Path(tiles.__file__).read_text(encoding="utf-8"))
    forbidden = ("vectis.simulation.engine", "vectis.realtime.pipeline", "vectis.agents")
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            assert not node.module.startswith(forbidden), node.module
        elif isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith(forbidden), alias.name


def test_build_tile_uses_only_screening_scores() -> None:
    # Pure-function check without the app: native res keeps one entry per screened cell.
    cells = build_tile([_hot_cell(), _mild_cell()], resolution=5)
    assert {c.cell_id for c in cells} == {assign_cell_id(*_HOT), assign_cell_id(*_MILD)}
    assert all(c.source_cells >= 1 for c in cells)


# ── Step 9: hierarchical fine-to-coarse roll-up, proven on a synthetic case ─────────────
def _sibling_native_cells() -> tuple[str, str, str]:
    """Two distinct res-5 cells that share one res-2 parent, plus that parent."""
    seed = assign_cell_id(*_HOT)
    parent = parent_cell_id(seed, 2)
    child_a, child_b = children_cell_ids(parent, 5)[:2]
    assert child_a != child_b
    return child_a, child_b, parent


def test_rollup_takes_the_max_per_hazard_over_a_known_synthetic_case() -> None:
    child_a, child_b, parent = _sibling_native_cells()
    hot = WorldCellState(cell_id=child_a, temperature=42.0, extra={"wind_speed_kmh": 70.0})
    mild = WorldCellState(cell_id=child_b, temperature=11.0)

    native = {c.cell_id: c for c in build_tile([hot, mild], resolution=5)}
    coarse = build_tile([hot, mild], resolution=2)

    assert len(coarse) == 1 and coarse[0].cell_id == parent
    # The documented aggregation: max per hazard — the hot child must survive un-averaged.
    expected = max(native[child_a].hazards["wildfire"], native[child_b].hazards["wildfire"])
    assert coarse[0].hazards["wildfire"] == expected
    assert coarse[0].hazards["wildfire"] == native[child_a].hazards["wildfire"]  # hot wins
    assert coarse[0].source_cells == 2  # both native cells contributed


def test_rollup_maxes_each_hazard_independently() -> None:
    child_a, child_b, parent = _sibling_native_cells()
    # A is the wildfire-hot cell, B is the flood-hot cell — the parent must take its
    # wildfire score from A and its flood score from B, never one child for both.
    a = WorldCellState(cell_id=child_a, temperature=42.0, flood_alert_level=1.0)
    b = WorldCellState(cell_id=child_b, temperature=11.0, flood_alert_level=3.0,
                       precipitation_mm=90.0)

    native = {c.cell_id: c for c in build_tile([a, b], resolution=5)}
    coarse = build_tile([a, b], resolution=2)[0]

    assert coarse.hazards["wildfire"] == native[child_a].hazards["wildfire"]
    assert coarse.hazards["flood"] == native[child_b].hazards["flood"]
    assert coarse.hazards["wildfire"] > native[child_b].hazards["wildfire"]
    assert coarse.hazards["flood"] > native[child_a].hazards["flood"]


def test_rollup_computes_on_demand_from_screening_data_round_trip() -> None:
    # parent/children helpers round-trip (Session 30), so every native cell lands on
    # exactly one coarse cell and no score can leak into a neighboring parent.
    child_a, child_b, parent = _sibling_native_cells()
    assert parent_cell_id(child_a, 2) == parent == parent_cell_id(child_b, 2)
    outsider = _mild_cell()  # a real California cell under a different res-2 parent
    coarse = build_tile(
        [WorldCellState(cell_id=child_a, temperature=42.0), outsider], resolution=2
    )
    by_id = {c.cell_id: c for c in coarse}
    assert set(by_id) == {parent, parent_cell_id(outsider.cell_id, 2)}
    assert all(c.source_cells == 1 for c in coarse)


# ── Step 10: tile caching — TTL + LRU keyed on contributing cell state versions ─────────
def test_cache_hits_on_identical_viewport_and_misses_when_a_contributing_cell_updates() -> None:
    import random
    import statistics
    import time as _time

    from vectis.realtime.state.store import MemoryStateStore

    rng = random.Random(36)
    store: MemoryStateStore[WorldCellState] = MemoryStateStore()
    # A real-shaped active set: 2,000 cells scattered over the western US.
    for _ in range(2_000):
        lat, lon = rng.uniform(31.0, 49.0), rng.uniform(-125.0, -102.0)
        store.save_state(
            WorldCellState(cell_id=assign_cell_id(lat, lon), temperature=rng.uniform(8.0, 42.0))
        )
    cache = TileCache()
    view_a = {"west": -125.0, "south": 32.0, "east": -114.0, "north": 42.0, "zoom": 8}
    view_b = {"west": -110.0, "south": 32.0, "east": -103.0, "north": 42.0, "zoom": 6}

    first = serve_tile(store, cache, **view_a)
    assert cache.misses == 1 and first.cells

    # Repeated pan/zoom over the same viewport: every call after the first is a hit,
    # and the hit path is sub-millisecond (median — the load-test claim, measured).
    timings = []
    for _ in range(50):
        start = _time.perf_counter()
        again = serve_tile(store, cache, **view_a)
        timings.append(_time.perf_counter() - start)
    assert cache.hits == 50 and again.cells == first.cells
    median = statistics.median(timings)
    print(f"\n[tiles] cache-hit median {median * 1000:.3f} ms over 50 calls (2,000-cell hot set)")
    assert median < 0.001, f"cache hit not sub-ms: {median * 1000:.3f} ms"

    # Warm a second, disjoint viewport…
    serve_tile(store, cache, **view_b)
    hits_before, misses_before = cache.hits, cache.misses

    # …then genuinely update one cell inside viewport A (version bumps, as the real
    # updater does): only A's tile is invalidated, B keeps hitting.
    victim = next(
        s for s in store.active_states()
        if -125.0 <= tiles._cell_center(s.cell_id)[1] <= -114.0
        and 32.0 <= tiles._cell_center(s.cell_id)[0] <= 42.0
    )
    updated = victim.model_copy(deep=True)
    updated.temperature = 44.0
    updated.version = victim.version + 1
    store.save_state(updated)

    hot_a = serve_tile(store, cache, **view_a)
    assert cache.misses == misses_before + 1  # A recomputed with the fresh state
    assert hot_a.cells != first.cells
    serve_tile(store, cache, **view_b)
    assert cache.hits == hits_before + 1  # B untouched by A's update — still a hit


def test_cache_ttl_expires_and_lru_bounds_memory() -> None:
    cache = TileCache(maxsize=2, ttl_seconds=10.0)
    unchanged = lambda ids: (1,) * len(ids)  # noqa: E731 — every member still at version 1
    cache.put("a", ["x"], (1,), [], now=0.0)
    assert cache.get("a", unchanged, now=5.0) == []  # fresh + versions match → hit
    assert cache.get("a", unchanged, now=11.0) is None  # expired → miss
    cache.put("a", ["x"], (1,), [], now=20.0)
    assert cache.get("a", lambda ids: (2,), now=21.0) is None  # version moved → miss
    cache.put("a", ["x"], (1,), [], now=20.0)
    cache.put("b", ["x"], (1,), [], now=21.0)
    cache.put("c", ["x"], (1,), [], now=22.0)  # evicts "a" (LRU, maxsize 2)
    assert len(cache) == 2
    assert cache.get("a", unchanged, now=23.0) is None
