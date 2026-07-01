"""Session 32 — the screening layer: abstraction, wildfire index, and the active-set sweep."""

from __future__ import annotations

import pytest

from vectis.core.schemas import RiskBand
from vectis.realtime.screening.base import (
    UNSCREENED_HAZARDS,
    NotYetScreenedIndex,
    ScreeningScore,
    register,
)


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
