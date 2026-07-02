"""Session 34 Step 4 — the out-of-sample backtest through the live pipeline.

Fixture-based, per the offline-first discipline: rows are drawn from a steep known
logistic (hot cell-days burn), so the live path *should* discriminate — proving the
harness measures skill, not that any real-world skill exists (no real FIRMS data was
ever available in this environment).
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pytest

from vectis.calibration.backtest import run_backtest, temporal_split
from vectis.calibration.data.dataset import LabeledCellDay


def _rows(n_days: int = 12, cells_per_day: int = 12, seed: int = 34) -> list[LabeledCellDay]:
    rng = np.random.default_rng(seed)
    day0 = date(2020, 8, 1)
    rows = []
    for d in range(n_days):
        for c in range(cells_per_day):
            temp = float(rng.normal(2.0, 6.0))
            wind = float(rng.normal(18.0, 8.0))
            z = -2.5 + 0.9 * temp + 0.05 * wind  # steep: temperature separates the classes
            fire = bool(rng.random() < 1.0 / (1.0 + np.exp(-z)))
            rows.append(
                LabeledCellDay(
                    cell_id=f"cell{c}", day=day0 + timedelta(days=d), lat=37.0, lon=-120.0,
                    temp_anomaly_c=temp, rainfall_anomaly_pct=float(rng.normal(0.0, 15.0)),
                    wind_speed_kmh=max(0.0, wind), fire=fire,
                )
            )
    return rows


def test_temporal_split_never_leaks_holdout_days_into_train() -> None:
    train, holdout, split_day = temporal_split(_rows(), holdout_fraction=0.3)
    assert train and holdout
    assert max(r.day for r in train) < split_day <= min(r.day for r in holdout)
    assert len({r.day for r in holdout}) == 4  # 0.3 × 12 days, rounded


def test_temporal_split_rejects_degenerate_inputs() -> None:
    with pytest.raises(ValueError, match="holdout_fraction"):
        temporal_split(_rows(), holdout_fraction=1.0)
    one_day = [r for r in _rows() if r.day == date(2020, 8, 1)]
    with pytest.raises(ValueError, match="two distinct days"):
        temporal_split(one_day)


def test_backtest_scores_out_of_sample_skill_through_the_live_path() -> None:
    report = run_backtest(_rows(), holdout_fraction=0.3, n_iterations=500, seed=34)

    assert report.n_train + report.n_holdout == 12 * 12
    assert 0 < report.n_fire_holdout < report.n_holdout
    # The generating signal is steep and the fit saw it — the replayed live path must
    # rank fire days above no-fire days well beyond coin-flipping.
    assert report.roc_auc > 0.7
    assert 0.0 <= report.brier <= 1.0
    assert sum(count for _, _, count in report.reliability) == report.n_holdout
    # The backlog is kept, so a recalibration map can be fit straight off the report.
    remap = report.calibrator.fit_recalibration("isotonic")
    assert 0.0 <= remap(0.5) <= 1.0
    # Provenance: the artifact records what was fit on (the train slice only).
    assert report.artifact["n_rows"] == report.n_train


def test_backtest_refuses_a_single_class_holdout() -> None:
    rows = [
        LabeledCellDay(
            cell_id="cell0", day=date(2020, 8, 1) + timedelta(days=d), lat=37.0, lon=-120.0,
            temp_anomaly_c=float(d % 7), rainfall_anomaly_pct=0.0, wind_speed_kmh=10.0,
            fire=d < 5,  # all fires early: the held-out tail is all no-fire
        )
        for d in range(20)
    ]
    with pytest.raises(ValueError, match="single outcome class"):
        run_backtest(rows, holdout_fraction=0.3, n_iterations=200)
