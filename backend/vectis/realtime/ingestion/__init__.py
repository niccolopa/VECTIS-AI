"""Ingestion — the edge of V3, where the outside world enters the system.

This subpackage holds the **source listeners and pollers** that connect to external
real-time feeds and turn whatever each one speaks (a FIRMS CSV row, an ERA5 grib
field, an MQTT sensor frame) into a uniform :class:`~vectis.realtime.events.GlobalEvent`.

Responsibilities (and, just as important, what it must *not* do):
- **Connect & parse** one external source each (NASA FIRMS, ERA5/Copernicus, IoT…),
  behind a small connector interface so sources are pluggable.
- **Emit** raw ``GlobalEvent`` onto a :mod:`~vectis.realtime.streams` stream — and
  then immediately move on. A listener is a thin, fast adapter.
- **Never block on computation.** Ingestion is decoupled from the estimator: it
  enqueues and returns (the V2 "202 Accepted + background work" principle, now over a
  durable stream). A slow downstream applies backpressure to the stream, never to the
  source — so a burst of events can never stall the listener or drop data.
- **No normalization or validation here** — that is the :mod:`~vectis.realtime.
  processors` stage. Listeners stay dumb so each is trivial to add and test.

Status: **blueprint** (Session 16) — connector stubs only; real network clients and
poll loops are implemented in later sessions.
"""

from __future__ import annotations
