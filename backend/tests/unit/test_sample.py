"""Unit tests for the deterministic sample generator."""

from __future__ import annotations

from vectis.data.pipeline.schema import LABEL, RAW_COLUMNS
from vectis.data.regions import CALIFORNIA
from vectis.scripts.generate_sample import build_frame


def test_sample_is_reproducible() -> None:
    a = build_frame(CALIFORNIA, seed=42)
    b = build_frame(CALIFORNIA, seed=42)
    assert a.equals(b)


def test_sample_shape_and_columns() -> None:
    df = build_frame(CALIFORNIA, seed=42)
    assert len(df) == CALIFORNIA.n_cells
    for col in [*RAW_COLUMNS, LABEL]:
        assert col in df.columns


def test_sample_has_both_classes() -> None:
    df = build_frame(CALIFORNIA, seed=42)
    # A learnable problem needs both fire and non-fire cells.
    assert 0 < df[LABEL].mean() < 1
