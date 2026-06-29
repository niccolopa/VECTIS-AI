"""Processors — turning raw events into clean Observations.

This subpackage is the boundary between *transport* and *math*. A processor consumes
raw :class:`~vectis.realtime.events.GlobalEvent`s off a stream and produces the
normalized ``Observation``s the :mod:`~vectis.realtime.state` estimator consumes.

The work, per stage:
- **Validate** — reject malformed, out-of-range, or stale events at the trust
  boundary (this is *not* an optional simplification — it is the input-validation
  layer for everything downstream).
- **Deduplicate** — collapse repeated reports of the same measurement (the same FIRMS
  pixel arriving twice) so the Bayesian/Kalman Update is not double-counted. Generalizes
  the V2 ``dedupe_key`` debounce to a global, streaming setting.
- **Normalize** — map each source's units/variable names onto the canonical
  ``WorldState`` variables, and attach the grid ``CellId`` the event falls in.
- **Window** — coalesce a burst of events for one cell into a single batched
  Observation, so the estimator's Update rate stays bounded under load (the key scale
  lever from ``docs/v3_realtime_architecture.md``).

Processors are pure and per-cell-independent: given the same events they emit the
same Observations, with no shared mutable state — so they parallelize by partition.

Status: **blueprint** (Session 16) — interfaces only; concrete validators,
deduplicators, and windowing land in later sessions.
"""

from __future__ import annotations
