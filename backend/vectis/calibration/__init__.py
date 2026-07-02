"""Calibration & validation — fitting and proving the hazard model against reality.

The Session-34 package. Everything under here exists to answer one question honestly:
*does the wildfire model's output mean something real?* It splits into:

- :mod:`vectis.calibration.data` — acquisition of historical FIRMS fire labels and ERA5
  weather, and the spatial-temporal join into a labeled training dataset.
- :mod:`vectis.calibration.fit` — fitting the logistic coefficients against that dataset.
- :mod:`vectis.calibration.backtest` — out-of-sample replay through the live forecasting
  path, scoring real predictive skill (ROC-AUC, Brier, reliability).

Threshold re-derivation is a *procedure*, not a module: after a real coefficient fit
lands, re-run the Session-32 gap measurement (``tests/realtime/test_screening.py``)
against the deployed model and re-derive ``TierManager``'s promotion constants from the
new gap table, the same way Session 33 derived them. Session 34 re-ran it with no
artifact deployed (no real fit was possible — no FIRMS credentials): the gap was
unchanged (MAD 3.61, max 13.23), so the Session-33 constants stand. See
``docs/calibration_report.md``.

Honesty contract (project-wide since V2, enforced here): calibration **never fabricates**.
If credentials or network are unavailable, the pipeline raises with instructions instead of
silently substituting synthetic data — a calibration number that wasn't measured is worse
than no number.
"""
