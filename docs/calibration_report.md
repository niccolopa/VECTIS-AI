# Wildfire Calibration Report — Session 34

> **⚠️ READ THIS FIRST — NO REAL CALIBRATION HAS HAPPENED.**
>
> This environment had **no FIRMS credentials and no CDS/ERA5 credentials at any point,
> across all three attempts at Session 34**. The entire fitting and backtesting pipeline
> described below **exists and is fully tested, but has never been run against real
> historical fire data**. Every metric in this report was produced from synthetic
> fixture data whose generating process we chose ourselves. The coefficients deployed
> in production are **still the Session-7 illustrative priors** — hand-tuned,
> directionally sensible, and **not validated against reality**. No confidence number
> the terminal displays should be treated as trustworthy until a real calibration run
> completes.

## What this session built (and proved, offline)

| Step | Deliverable | Status |
|---|---|---|
| 1 | Historical data acquisition (`vectis/calibration/data/`) | Built + tested; **never run live** |
| 2 | Spatial-temporal join → labeled cell-day dataset | Built + tested; **never run live** |
| 3 | Coefficient fitting (`vectis/calibration/fit.py`) + artifact loader | Built + tested; **no artifact produced** |
| 4 | Backtesting harness (`vectis/calibration/backtest.py`) | Built + tested on fixtures only |
| 5 | Running Brier / reliability from resolved live forecasts | Built + tested |
| 6 | Tiering-threshold re-derivation | Re-measured; **no change — justified below** |

## Credentials a future session needs

Only **one** credential is required to run the whole pipeline live:

- **`VECTIS_FIRMS_API_KEY`** — a free NASA FIRMS MAP_KEY, obtained in minutes at
  <https://firms.modaps.eosdis.nasa.gov/api/map_key/>. This unlocks the historical
  standard-processing archive (`VIIRS_SNPP_SP`) that provides the fire/no-fire labels.
  Alternatively, point `VECTIS_FIRMS_BASE_URL` at a running Sluice gateway that holds
  the key.
- **ERA5 weather needs no credential**: the pipeline deliberately uses Open-Meteo's
  keyless `/v1/era5` archive endpoint (the same Copernicus ERA5 data), so
  `VECTIS_CDS_API_KEY` / a CDS account is **not** required. The `cdsapi` route only
  pays off for bulk gridded pulls far beyond this per-cell join.

With the key set, the full run is two commands from `backend/`:

```
python -m vectis.calibration.data.build --region california --start 2020-06-01 --end 2020-10-31
python -m vectis.calibration.fit data/processed/calibration/wildfire_california_2020-06-01_2020-10-31.csv
python -m vectis.calibration.backtest data/processed/calibration/wildfire_california_2020-06-01_2020-10-31.csv
```

The fit writes `backend/artifacts/calibration/wildfire_coefficients.json`;
`default_wildfire_model()` picks it up automatically — the Monte Carlo engine and the
screening index both construct through that one seam, so deploying a real fit is a pure
parameter change with no code edit.

## Fitted vs. illustrative coefficients

No real fit was possible, so the honest answer is a single column:

| Feature | Deployed value | Provenance |
|---|---|---|
| intercept | −1.5 | Session-7 illustrative prior |
| `temp_anomaly_c` | 0.55 | Session-7 illustrative prior |
| `rainfall_anomaly_pct` | −0.03 | Session-7 illustrative prior |
| `wind_speed_kmh` | 0.06 | Session-7 illustrative prior |
| `ignition_sources` | 0.40 | Session-7 illustrative prior — **and will remain a prior even after a real fit**: FIRMS/ERA5 carry no ignition observable, so the fitter carries it forward unchanged and records that in the artifact |

The fitter itself is proven: on synthetic datasets drawn from a known logistic it
recovers the generating intercept and coefficients (see
`backend/tests/calibration/test_fit.py`). That demonstrates the machinery works — it
says **nothing** about whether the priors above resemble reality.

## Backtest results (fixture data — not real-world skill)

The harness (`run_backtest`) temporally splits a labeled dataset (train strictly
precedes holdout; no leakage), fits on the early slice, and replays the held-out
cell-days through the **actual live path** — the same Kalman filter, Bayesian updater,
and Monte Carlo hazard evaluation that serve production, via
`ContinuousPipeline.replay_observations`. It reports ROC-AUC, Brier score, and a
reliability curve, and completes the Session-8 `Calibrator` stubs
(`reliability_curve`, `fit_recalibration` — isotonic and Platt).

On the synthetic fixture (a steep known logistic), the replayed live path scores
ROC-AUC > 0.7 out of sample — asserted as a regression guard in
`test_backtest.py`, **not reported as evidence of real predictive skill**. There is no
real number to report here, and inventing one is exactly what this project refuses
to do.

Two serve-time gaps the backtest deliberately preserves (they are part of what a real
backtest must measure):
- Only temperature and wind flow through the live Kalman path; rainfall anomaly and
  ignition sources stay at the digital-twin baseline, exactly as at serve time.
- The headline risk (0–100) is scored as a probability. Whether that reading is
  calibrated is precisely what the reliability curve and `fit_recalibration` exist to
  measure and correct — on real outcomes, when they exist.

## Threshold re-derivation: explicitly unchanged

Session 33 derived `TierManager`'s promotion constants (transition band **[5, 85)**,
unconditional cutoff **85**, priority bias correction **+13.23**) from the measured
Session-32 screening-vs-engine gap table. Step 6 re-ran that measurement against the
model actually deployed after Step 3. Because no calibration artifact exists, the
deployed model is byte-for-byte the same prior model — and the re-measured gap is
identical: **MAD 3.61, max 13.23**. The constants therefore remain exactly derived
from a still-valid measurement and were **deliberately left untouched**; changing them
would have been activity, not information. When a real fit lands, re-run
`tests/realtime/test_screening.py`'s gap measurement and re-derive the constants from
the new table, the same way Session 33 did.

## Limitations

Stated for completeness, and honestly: **most of these are moot in this report because
no real sample was ever used** — they become live concerns the day a real calibration
runs.

- **No real data, period.** The dominant limitation of everything above. All others
  are subordinate to it.
- **Sample representativeness — n/a here.** No real sample was used, so nothing can be
  said about its representativeness. A future real fit on (say) California 2020 must
  ask whether one region-season generalizes across fuel types, terrain, and climate
  regimes before its coefficients are trusted globally.
- **Arson / human ignition.** `ignition_sources` is not observable from FIRMS/ERA5 and
  is carried at its prior even after a real fit. Deliberate and accidental human
  ignition — a major real-world driver — is outside what this dataset can identify.
- **Sub-grid wind.** ERA5 wind at H3 resolution-5 (~8.5 km cells) cannot resolve
  canyon channeling, downslope wind events, or local gust structure that drive real
  fire behaviour. Daily-max aggregation captures the worst hour, not the worst ridge.
- **Detection ≠ ignition.** FIRMS labels are satellite *detections*: cloud cover,
  overpass timing, and small/short fires all produce false negatives in the labels
  themselves.
- **Climatology baseline.** The ~22 °C anomaly baseline is still the hand-set constant
  shared by the live bridge and the join (kept identical for fit/serve consistency).
  Per-cell climatology remains future work.
