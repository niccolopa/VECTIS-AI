"""Calibration & validation — fitting and proving the hazard model against reality.

The Session-34 package. Everything under here exists to answer one question honestly:
*does the wildfire model's output mean something real?* It splits into:

- :mod:`vectis.calibration.data` — acquisition of historical FIRMS fire labels and ERA5
  weather, and the spatial-temporal join into a labeled training dataset.
- :mod:`vectis.calibration.fit` — fitting the logistic coefficients against that dataset.
- :mod:`vectis.calibration.backtest` — out-of-sample replay through the live forecasting
  path, scoring real predictive skill (ROC-AUC, Brier, reliability).
- :mod:`vectis.calibration.thresholds` — re-deriving the tiering promotion thresholds
  from the (re)calibrated model's measured error curve.

Honesty contract (project-wide since V2, enforced here): calibration **never fabricates**.
If credentials or network are unavailable, the pipeline raises with instructions instead of
silently substituting synthetic data — a calibration number that wasn't measured is worse
than no number.
"""
