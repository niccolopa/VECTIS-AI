"""Out-of-sample backtest: replay held-out cell-days through the live forecasting path.

The harness answers the question calibration exists for: *when the pipeline said X%,
how often did a fire actually follow?* It temporally splits the labeled FIRMS × ERA5
dataset, fits the logistic on the **earlier** slice (:mod:`vectis.calibration.fit`),
then replays the **later** slice — day by day, cell by cell — through the *actual*
live components via :meth:`ContinuousPipeline.replay_observations`: the same Kalman
filter, the same Bayesian updater, the same Monte Carlo hazard evaluation that serves
production forecasts. The headline risk (0–100, read as a probability) is scored
against the FIRMS outcome with ROC-AUC, Brier score, and the reliability curve.

Honest scope notes:

- Only the variables the live path actually ingests (temperature, wind) are replayed;
  rainfall anomaly and ignition sources stay at the digital-twin baseline **exactly as
  at serve time** — that fit/serve gap is part of what the backtest measures, not a
  shortcut around it.
- The replay drives whatever dataset it is given. In an environment with no FIRMS
  MAP_KEY (this one, for all of Session 34), that means fixture/synthetic rows: the
  harness is proven, but no metric it has produced here describes real-world skill.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from pathlib import Path
from typing import Any

from sklearn.metrics import roc_auc_score

from vectis.calibration.data.dataset import LabeledCellDay, read_dataset
from vectis.calibration.fit import fit_wildfire_coefficients
from vectis.core.logging import get_logger
from vectis.realtime.events.base import GlobalObservation
from vectis.realtime.pipeline import build_default_pipeline
from vectis.realtime.screening.wildfire import _CLIMATOLOGY_TEMP_C
from vectis.simulation.engine.runner import VectorizedMonteCarloEngine
from vectis.simulation.models.wildfire import WildfireHazardModel
from vectis.simulation.probability.calibration import Calibrator

logger = get_logger(__name__)

_SOURCE = "calibration-backtest"


@dataclass(frozen=True)
class BacktestReport:
    """Out-of-sample skill of the live path, plus the backlog that produced it."""

    split_day: date  # first held-out day — everything from here on was never fit on
    n_train: int
    n_holdout: int
    n_fire_holdout: int
    roc_auc: float
    brier: float
    reliability: list[tuple[float, float, int]]
    calibrator: Calibrator  # keep the backlog: fit_recalibration() runs off it
    artifact: dict[str, Any]  # the train-slice coefficient fit, with provenance


def temporal_split(
    rows: list[LabeledCellDay], holdout_fraction: float = 0.3
) -> tuple[list[LabeledCellDay], list[LabeledCellDay], date]:
    """Split by calendar day — train strictly precedes holdout, so nothing leaks back.

    A shuffled split would let the model train on the *same day* it is scored on
    (weather is autocorrelated); a temporal split is the only honest one here.
    """
    if not 0.0 < holdout_fraction < 1.0:
        raise ValueError("holdout_fraction must be in (0, 1)")
    days = sorted({r.day for r in rows})
    if len(days) < 2:
        raise ValueError("temporal split needs at least two distinct days")
    n_holdout_days = min(max(1, round(holdout_fraction * len(days))), len(days) - 1)
    split_day = days[len(days) - n_holdout_days]
    train = [r for r in rows if r.day < split_day]
    holdout = [r for r in rows if r.day >= split_day]
    return train, holdout, split_day


def run_backtest(
    rows: list[LabeledCellDay],
    *,
    holdout_fraction: float = 0.3,
    n_iterations: int = 2_000,
    seed: int = 34,
    n_bins: int = 10,
) -> BacktestReport:
    """Fit on the early slice, replay the late slice through the live path, score it."""
    train, holdout, split_day = temporal_split(rows, holdout_fraction)
    if not any(r.fire for r in holdout) or all(r.fire for r in holdout):
        raise ValueError(
            "held-out slice has a single outcome class — ROC-AUC and reliability are "
            "undefined; widen the window or lower holdout_fraction"
        )

    artifact = fit_wildfire_coefficients(train)
    model = WildfireHazardModel(
        intercept=artifact["intercept"], coefficients=dict(artifact["coefficients"])
    )
    pipeline = build_default_pipeline(
        engine=VectorizedMonteCarloEngine(hazard=model),
        n_iterations=n_iterations,
        seed=seed,
    )

    calibrator = Calibrator()
    for row in sorted(holdout, key=lambda r: (r.day, r.cell_id)):
        observed_at = datetime.combine(row.day, time(12, tzinfo=UTC))
        result = pipeline.replay_observations([
            GlobalObservation(
                cell_id=row.cell_id,
                variable="temperature",  # live feeds report absolute °C — reverse the anomaly
                value=row.temp_anomaly_c + _CLIMATOLOGY_TEMP_C,
                observed_at=observed_at,
                source=_SOURCE,
            ),
            GlobalObservation(
                cell_id=row.cell_id,
                variable="wind_speed_kmh",
                value=row.wind_speed_kmh,
                observed_at=observed_at,
                source=_SOURCE,
            ),
        ])
        calibrator.record(result.risk_score / 100.0, row.fire)

    predicted = [r.predicted for r in calibrator.records]
    outcomes = [r.occurred for r in calibrator.records]
    report = BacktestReport(
        split_day=split_day,
        n_train=len(train),
        n_holdout=len(holdout),
        n_fire_holdout=sum(outcomes),
        roc_auc=float(roc_auc_score(outcomes, predicted)),
        brier=calibrator.brier(),
        reliability=calibrator.reliability_curve(n_bins),
        calibrator=calibrator,
        artifact=artifact,
    )
    logger.info(
        "[INFO] backtest: %d train / %d holdout (split %s) — ROC-AUC %.3f, Brier %.4f",
        report.n_train, report.n_holdout, split_day, report.roc_auc, report.brier,
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path, help="labeled CSV from vectis.calibration.data.build")
    parser.add_argument("--holdout-fraction", type=float, default=0.3)
    parser.add_argument("--n-iterations", type=int, default=2_000)
    args = parser.parse_args(argv)

    report = run_backtest(
        read_dataset(args.dataset),
        holdout_fraction=args.holdout_fraction,
        n_iterations=args.n_iterations,
    )
    print(
        f"holdout from {report.split_day}: {report.n_holdout} cell-days "
        f"({report.n_fire_holdout} fire)\n"
        f"ROC-AUC {report.roc_auc:.3f}  Brier {report.brier:.4f}"
    )
    for mean_pred, obs_freq, count in report.reliability:
        print(f"  predicted {mean_pred:.2f} -> observed {obs_freq:.2f}  (n={count})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
