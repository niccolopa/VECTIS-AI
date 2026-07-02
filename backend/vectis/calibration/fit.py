"""Fit the wildfire logistic coefficients against the labeled FIRMS × ERA5 dataset.

A standard, auditable fit — :class:`sklearn.linear_model.LogisticRegression` with **no
penalty** (the model *is* a plain logistic; a regularized fit would silently shrink the
coefficients the rest of the system treats as physical effect sizes). The fitted model is
the exact functional form :class:`WildfireHazardModel` evaluates, so swapping coefficients
is a pure parameter change: the Monte Carlo engine, the Bayesian updater, and the
screening layer run unmodified.

What is fit and what is carried
-------------------------------
Only the features the dataset can actually observe are fit: ``temp_anomaly_c``,
``rainfall_anomaly_pct``, ``wind_speed_kmh``. The ``ignition_sources`` coefficient is
**carried forward unchanged** from the illustrative priors and recorded as such in the
artifact — FIRMS/ERA5 carry no ignition observable, and a coefficient the data cannot
identify must not be presented as fitted.

The artifact (``artifacts/calibration/wildfire_coefficients.json``) carries the fitted
values *plus provenance* (dataset manifest, row counts, timestamp) and the old
illustrative values for the audit trail. :func:`vectis.simulation.models.wildfire
.default_wildfire_model` picks it up when present.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.linear_model import LogisticRegression

from vectis.calibration.data.dataset import LabeledCellDay, read_dataset
from vectis.core.config import get_settings
from vectis.core.logging import get_logger
from vectis.simulation.models.wildfire import _DEFAULT_COEFFICIENTS

logger = get_logger(__name__)

#: Features the FIRMS × ERA5 dataset observes — the only coefficients a fit can identify.
FITTED_FEATURES = ("temp_anomaly_c", "rainfall_anomaly_pct", "wind_speed_kmh")


def fit_wildfire_coefficients(
    rows: Sequence[LabeledCellDay], *, manifest: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Fit the logistic on labeled cell-days and return the coefficient artifact."""
    fires = sum(r.fire for r in rows)
    if fires == 0 or fires == len(rows):
        raise ValueError(
            f"cannot fit a discriminative model on {fires} fire / {len(rows) - fires} "
            "no-fire rows — both outcomes are required"
        )
    x = np.array(
        [[r.temp_anomaly_c, r.rainfall_anomaly_pct, r.wind_speed_kmh] for r in rows]
    )
    y = np.array([r.fire for r in rows], dtype=int)

    # penalty=None: the plain (unregularized) logistic the hazard model evaluates.
    fitted = LogisticRegression(penalty=None, max_iter=2000).fit(x, y)
    coefficients = dict(zip(FITTED_FEATURES, (float(c) for c in fitted.coef_[0]), strict=True))
    # Unidentifiable from this dataset — carried at the illustrative prior, and said so.
    coefficients["ignition_sources"] = _DEFAULT_COEFFICIENTS["ignition_sources"]

    artifact = {
        "model": "wildfire_logistic",
        "intercept": float(fitted.intercept_[0]),
        "coefficients": coefficients,
        "features_fit": list(FITTED_FEATURES),
        "carried_forward": {"ignition_sources": _DEFAULT_COEFFICIENTS["ignition_sources"]},
        "illustrative_previous": {"intercept": -1.5, "coefficients": dict(_DEFAULT_COEFFICIENTS)},
        "n_rows": len(rows),
        "n_fire": int(fires),
        "fitted_at": datetime.now(UTC).isoformat(),
        "dataset_manifest": manifest,
    }
    logger.info(
        "[INFO] fitted wildfire logistic on %d rows (%d fire): intercept=%.4f %s",
        len(rows), fires, artifact["intercept"],
        {k: round(v, 4) for k, v in coefficients.items()},
    )
    return artifact


def write_coefficients(artifact: dict[str, Any], path: Path | None = None) -> Path:
    """Persist the artifact where :func:`default_wildfire_model` looks for it."""
    if path is None:
        path = get_settings().artifacts_dir / "calibration" / "wildfire_coefficients.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    logger.info("[INFO] wrote calibrated coefficients to %s", path)
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path, help="labeled CSV from vectis.calibration.data.build")
    args = parser.parse_args(argv)

    manifest_path = args.dataset.with_name(args.dataset.stem + ".manifest.json")
    manifest = (
        json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else None
    )
    artifact = fit_wildfire_coefficients(read_dataset(args.dataset), manifest=manifest)
    path = write_coefficients(artifact)
    print(f"fitted on {artifact['n_rows']} rows ({artifact['n_fire']} fire) -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
