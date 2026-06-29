"""VECTIS V3 — the Real-Time Global Intelligence layer.

Where V2 produced *possible worlds* for one region on demand, V3 is a **living
system**: it continuously observes the *entire world* through real-time data
streams, maintains an always-current estimate of the global state, and keeps the
probabilities of every future continuously updated.

This package is the streaming, global, continuous layer that wraps — and reuses —
the V2 engines (Monte Carlo, Bayesian update, scenarios). It does **not** replace
them; it feeds them from a never-ending stream instead of a single endpoint call.

The pipeline, stage by stage (each a subpackage with a distinct type contract)::

    ingestion → events → streams → processors → state → forecasting
       │          │         │          │          │         │
    source     raw       continuous  validate/   continuous continuous
    listeners  Event     flow        normalize   State +    Forecast
                         pipeline    → Observation Update

Subpackages:
- :mod:`~vectis.realtime.ingestion`   source listeners/pollers → raw events
- :mod:`~vectis.realtime.events`      global Event / Observation schemas
- :mod:`~vectis.realtime.streams`     continuous flow: partition, route, backpressure
- :mod:`~vectis.realtime.processors`  validate · dedupe · normalize · window
- :mod:`~vectis.realtime.state`       continuous global state estimation (Kalman/Bayes)
- :mod:`~vectis.realtime.forecasting` continuous prediction output

Design docs: ``docs/v3_realtime_architecture.md``, ``docs/v3_state_management.md``.

Status: **blueprint** (Session 16). Interfaces and schemas only — the concrete
stream processors, Kalman filters, and Kafka/WebSocket transports land in later
sessions. The Math Firewall still holds: nothing here lets an LLM touch a number.
"""

from __future__ import annotations
