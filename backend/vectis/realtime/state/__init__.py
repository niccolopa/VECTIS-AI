"""State — the continuously-estimated representation of the whole world.

This is the living core of V3. Where V2 held one ``RegionTwin`` for Liguria, V3
maintains a **global state field**: for every active cell on a world grid, the
current estimate of its physical variables *and the uncertainty around them* (mean +
covariance), kept current by a streaming filter that never recomputes from scratch.

What lives here:
- the **GlobalState** — a sparse collection of per-cell estimates (only cells with
  recent data are materialized; the globe is mostly empty at any instant);
- the :class:`StateEstimator` ABC — the continuous-stream **Update** engine,
  generalizing V2's on-demand Bayesian update into an always-on **predict–correct**
  loop (Kalman filter for continuous variables; the reused V2 Bayesian updater for the
  discrete scenario belief).

Why it scales to thousands of events/min:
- per-cell independence → horizontal sharding, no global lock;
- incremental **O(1)** Updates → throughput independent of event history (no replay);
- sparse, aged state → memory tracks *activity*, not planetary area;
- batch-friendly Update → bursts collapse into one Update per window.

The filter math is pure ``numpy``/``scipy`` and, like all of the simulation layer,
never imports the agents/LLM layer — the Math Firewall holds at global scale.

Design: ``docs/v3_state_management.md``.

Status: **blueprint** (Session 16) — :class:`StateEstimator` ABC defined in
``base.py``; the first concrete Kalman estimator lands in Session 17.
"""

from __future__ import annotations

from vectis.realtime.state.base import CellState, GlobalState, StateEstimator

__all__ = ["CellState", "GlobalState", "StateEstimator"]
