"""Events — the global wire-format schemas of V3.

This subpackage defines the typed payloads that cross the V3 boundary, in two
directions and at two levels of trust:

- :class:`GlobalEvent` — **raw, untrusted** data as it leaves a source. It is the
  V3 generalization of the V2 ``StreamEvent``: where V2 events carried a single
  ``region: str``, a ``GlobalEvent`` carries **global geospatial scope** (lat/lon and
  the grid cell it falls in) plus source/ingest provenance and an opaque payload. It
  makes *no* claim of correctness — that is earned in the processor stage.
- (later) global ``Observation`` — an Event after validation/normalization, ready for
  the estimator. The clean line between *transport* (Event) and *math* (Observation)
  mirrors V2's ``StreamEvent`` vs ``Observation`` split, lifted to global scope.

Keeping these as pure, picklable Pydantic models (no behavior beyond a translation
hook) is what lets the same event flow through an in-process stub today and a Kafka
topic tomorrow without change.

Status: **blueprint** (Session 16) — :class:`GlobalEvent` base defined in
``base.py``; concrete source events (FIRMS, ERA5…) and the global ``Observation``
arrive with their processors.
"""

from __future__ import annotations
