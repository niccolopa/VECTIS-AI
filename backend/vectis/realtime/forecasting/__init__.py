"""Forecasting — the continuous prediction output of V3.

Because the :mod:`~vectis.realtime.state` field is always current, the forecast can
be too. This subpackage projects each cell's live state forward into a distribution
over outcomes by feeding it to the **reused V2 Monte Carlo engine** — turning a
continuously-estimated present into a continuously-updated future.

The inversion that defines V3: consumers do not *request* a forecast for a cell (at
global scale there are far too many, changing constantly). Instead, forecasts are
produced as state changes and consumers **subscribe** to the cells/regions they care
about. Computation happens once, on update — not once per reader.

What lives here:
- the **Forecast** output schema — a distribution (with bands/percentiles, like the
  V2 ``ProbabilityDistribution``) tagged with its cell, horizon, and the state version
  it was drawn from, so every forecast is reproducible and auditable;
- the continuous forecaster that maps ``CellState`` → Monte Carlo run → ``Forecast``,
  drawing from the *distribution* of the state (mean + covariance), not a point — so
  state uncertainty propagates into forecast uncertainty.

Status: **blueprint** (Session 16) — schema/interface only; the continuous forecaster
is wired once the estimator exists (Session 17+).
"""

from __future__ import annotations
