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
from vectis.realtime.screening.wildfire import WildfireScreeningIndex
from vectis.realtime.state.models import WorldCellState


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
