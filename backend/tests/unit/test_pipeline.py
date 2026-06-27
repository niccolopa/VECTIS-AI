"""Unit tests for the data pipeline stages and runner."""

from __future__ import annotations

import pandas as pd
import pytest

from vectis.core.exceptions import DataValidationError
from vectis.data.connectors import get_connector
from vectis.data.pipeline import steps
from vectis.data.pipeline.runner import run_pipeline
from vectis.data.pipeline.schema import FEATURE_NAMES, LABEL
from vectis.data.regions import get_region


def _raw_frame() -> pd.DataFrame:
    return get_connector("sample").fetch(get_region("liguria")).frame.copy()


def test_validate_rejects_missing_columns() -> None:
    df = _raw_frame().drop(columns=["drought_index"])
    with pytest.raises(DataValidationError):
        steps.validate(df)


def test_validate_rejects_out_of_range() -> None:
    df = _raw_frame()
    df.loc[0, "humidity_pct"] = 999
    with pytest.raises(DataValidationError):
        steps.validate(df)


def test_engineer_features_produces_model_columns() -> None:
    df = steps.engineer_features(steps.clean(steps.validate(_raw_frame())))
    for feature in FEATURE_NAMES:
        assert feature in df.columns
    assert df[FEATURE_NAMES].notna().all().all()


def test_clean_deduplicates_cells() -> None:
    df = _raw_frame()
    doubled = pd.concat([df, df.iloc[[0]]], ignore_index=True)
    assert len(steps.clean(doubled)) == len(df)


def test_run_pipeline_is_deterministic(pipeline_result) -> None:
    again = run_pipeline(get_connector("sample").fetch(get_region("liguria")),
                         require_label=True)
    assert pipeline_result.dataset_version == again.dataset_version
    assert pipeline_result.has_label and LABEL in pipeline_result.features.columns
