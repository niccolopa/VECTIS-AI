"""Session 32 — the screening layer: abstraction, wildfire index, and the active-set sweep."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from vectis.core.schemas import RiskBand
from vectis.realtime.screening.base import (
    UNSCREENED_HAZARDS,
    NotYetScreenedIndex,
    ScreeningScore,
    default_registry,
    register,
)
from vectis.realtime.screening.sweep import GlobalScreeningSweep
from vectis.realtime.screening.wildfire import WildfireScreeningIndex
from vectis.realtime.state.models import WorldCellState
from vectis.realtime.state.store import EvictingStateStore, MemoryStateStore


def test_screening_score_bands_on_the_shared_scale() -> None:
    assert ScreeningScore("wildfire", 90.0).band is RiskBand.SEVERE
    assert ScreeningScore("wildfire", 10.0).band is RiskBand.LOW


def test_unscreened_hazards_have_no_model_and_raise_instead_of_faking() -> None:
    # The honest stub: an unmodelled hazard raises rather than returning a plausible number.
    for hazard in UNSCREENED_HAZARDS:
        with pytest.raises(NotImplementedError):
            NotYetScreenedIndex(hazard).score([])


def test_register_requires_a_hazard_key() -> None:
    stub = NotYetScreenedIndex("")  # empty hazard
    with pytest.raises(ValueError):
        register(stub)


# ── wildfire index ─────────────────────────────────────────────────────────────────────
def test_wildfire_is_the_only_registered_hazard_today() -> None:
    assert set(default_registry()) == {"wildfire"}


def test_wildfire_screen_ranks_hotter_drier_cells_higher() -> None:
    hot = WorldCellState(cell_id="hot", temperature=34.0, extra={"wind_speed_kmh": 50.0})
    mild = WorldCellState(cell_id="mild", temperature=16.0, extra={"wind_speed_kmh": 3.0})
    scores = WildfireScreeningIndex().score([hot, mild])
    assert scores["hot"].value > scores["mild"].value
    assert all(0.0 <= s.value <= 100.0 for s in scores.values())


def test_wildfire_screen_skips_cells_with_no_wildfire_state() -> None:
    # A cyclone-only GDACS cell carries no temperature — it must be skipped, not fabricated.
    cyclone_only = WorldCellState(cell_id="cyc", extra={"cyclone_alert_level": 3.0})
    hot = WorldCellState(cell_id="hot", temperature=30.0)
    scores = WildfireScreeningIndex().score([cyclone_only, hot])
    assert "cyc" not in scores
    assert "hot" in scores


def test_wildfire_screen_handles_missing_wind_via_baseline() -> None:
    # Temperature present, wind absent from extra: scores (using the baseline wind), no crash.
    scores = WildfireScreeningIndex().score([WorldCellState(cell_id="c", temperature=28.0)])
    assert 0.0 <= scores["c"].value <= 100.0


def test_screening_does_not_import_the_monte_carlo_engine() -> None:
    # Screening and simulation must be independent code paths that only share the hazard
    # function. Prove it by parsing the imports of each screening module: none may import
    # from vectis.simulation.engine. (The `vectis.realtime` package __init__ eagerly imports
    # the pipeline for unrelated reasons, so a sys.modules check would catch that pre-existing
    # coupling, not ours — what matters is screening's own code never importing the engine.)
    import vectis.realtime.screening.base as base_mod
    import vectis.realtime.screening.wildfire as wf_mod

    for mod in (base_mod, wf_mod):
        assert mod.__file__ is not None
        tree = ast.parse(Path(mod.__file__).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.startswith("vectis.simulation.engine"), (
                    f"{mod.__name__} imports the MC engine: {node.module}"
                )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("vectis.simulation.engine"), (
                        f"{mod.__name__} imports the MC engine: {alias.name}"
                    )


# ── the active-set sweep ─────────────────────────────────────────────────────────────────
def test_sweep_returns_flat_cell_to_hazard_scores() -> None:
    cells = [
        WorldCellState(cell_id="a", temperature=31.0, extra={"wind_speed_kmh": 40.0}),
        WorldCellState(cell_id="b", temperature=15.0),
    ]
    result = GlobalScreeningSweep().sweep(cells)
    assert result["a"]["wildfire"].value > result["b"]["wildfire"].value
    assert set(result["a"]) == {"wildfire"}  # only the modelled hazard appears


def test_sweep_skips_cells_with_no_screenable_state() -> None:
    # A cyclone-only cell has no wildfire state and no other model — it is absent entirely,
    # never a fabricated number.
    cells = [
        WorldCellState(cell_id="fire", temperature=30.0),
        WorldCellState(cell_id="cyc", extra={"cyclone_alert_level": 3.0}),
    ]
    result = GlobalScreeningSweep().sweep(cells)
    assert "fire" in result
    assert "cyc" not in result


def test_sweep_store_touches_only_the_hot_set_not_the_grid() -> None:
    # EvictingStateStore's hot set is bounded; a swept store must screen exactly those cells.
    store: EvictingStateStore[WorldCellState] = EvictingStateStore(
        MemoryStateStore(), maxsize=2
    )
    for i in range(5):  # 5 writes, maxsize 2 → only the last 2 survive in the hot set
        store.save_state(WorldCellState(cell_id=f"c{i}", temperature=20.0 + i))

    result = GlobalScreeningSweep().sweep_store(store)
    assert set(result) == {"c3", "c4"}, "sweep must see only the active (hot) cells"
    assert store.active_cells == 2


def test_empty_store_sweep_is_empty() -> None:
    store: MemoryStateStore[WorldCellState] = MemoryStateStore()
    assert GlobalScreeningSweep().sweep_store(store) == {}


# ── Step 4: screening ≠ simulation — the gap, measured not assumed ───────────────────────
# Observed gap of the wildfire screen (a single baseline-scenario point estimate) against
# the full VectorizedMonteCarloEngine + prior-mixture risk, over a temperature sweep at the
# California baseline (40k draws, seed=32, n_workers=1). Screening is decoupled from the
# engine; they share only the logistic hazard, so the difference is exactly {scenario mixture
# + sampling nonlinearity}:
#
#     temp   screen   engine    diff
#     12.0     0.76     1.85   -1.09
#     16.0     6.45    13.33   -6.88
#     20.0    38.34    51.58  -13.23   <- steep transition band: the largest gap
#     24.0    84.88    88.45   -3.57
#     28.0    98.06    98.48   -0.42
#     32.0    99.78    99.83   -0.05
#     36.0    99.98    99.98   -0.01
#
#     MAD = 3.61 (n=7), max = 13.23
#
# Reading: the screen matches the engine within ~1 point where risk saturates (both near 0
# or 100), but under-estimates by up to ~13 points in the mid-risk transition band, always
# biased LOW (it omits the upward hotter_drier/extreme_wind scenarios the engine mixes in).
# This is the number Session 33's promotion threshold should respect: screen aggressively in
# the saturated tails, but promote mid-band cells to the full engine, where the gap is largest
# and the decision most sensitive. The asserts below are regression guards around the measured
# gap, not an arbitrary "close enough" — a broken screen (e.g. a wrong climatology offset)
# blows straight past them.
def test_screening_gap_vs_full_engine_is_measured_and_bounded() -> None:
    from vectis.simulation.engine.runner import VectorizedMonteCarloEngine
    from vectis.simulation.probability.uncertainty import posterior_mixture_risk
    from vectis.simulation.scenarios.generator import (
        WildfireScenarioGenerator,
        california_wildfire_state,
    )
    from vectis.simulation.schemas import SimulationConfig

    climatology, baseline_wind = 22.0, 35.0
    temps = [12.0, 16.0, 20.0, 24.0, 28.0, 32.0, 36.0]
    cells = [
        WorldCellState(cell_id=f"t{t}", temperature=t, extra={"wind_speed_kmh": baseline_wind})
        for t in temps
    ]
    screen = WildfireScreeningIndex().score(cells)

    engine = VectorizedMonteCarloEngine()
    gen = WildfireScenarioGenerator()
    config = SimulationConfig(n_iterations=40_000, seed=32, n_workers=1, parallel=False)

    diffs, worst_full = [], 0.0
    worst = 0.0
    for cell in cells:
        assert cell.temperature is not None  # constructed with a temperature above
        state = california_wildfire_state()
        by = {v.name: v for v in state.variables}
        by["temp_anomaly_c"].value = cell.temperature - climatology
        by["wind_speed_kmh"].value = cell.extra["wind_speed_kmh"]
        scenarios = gen.generate(state)
        run = engine.run(state, scenarios, config)
        full = posterior_mixture_risk(scenarios, {o.scenario_id: o.risk.mean for o in run.outcomes})
        s = screen[cell.cell_id].value

        assert 0.0 <= s <= 100.0 and 0.0 <= full <= 100.0
        # The screen omits the upward scenarios, so it must not materially OVER-estimate.
        assert s <= full + 2.0, (cell.temperature, s, full)
        if abs(s - full) > worst:
            worst, worst_full = abs(s - full), full
        diffs.append(abs(s - full))

    mad = sum(diffs) / len(diffs)
    print(f"\nscreening vs full-engine gap: MAD={mad:.2f}, max={max(diffs):.2f} (n={len(diffs)})")

    # Regression guards informed by the measured gap (MAD~3.6, max~13.2), not arbitrary.
    assert mad < 8.0, mad
    assert max(diffs) < 20.0, max(diffs)
    # The worst gap lives in the unsaturated transition band, not the tails — that is where
    # promotion to the full engine actually buys accuracy.
    assert 10.0 < worst_full < 90.0, worst_full
