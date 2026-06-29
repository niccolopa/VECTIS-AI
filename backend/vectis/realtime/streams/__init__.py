"""Streams — the continuous flow pipeline that carries events through V3.

A **Stream** is the transport backbone between ingestion and processing. It owns
exactly the concerns the math layer must never see:

- **Partitioning** by grid cell — the global grid is the shard key, so each cell's
  events form an independent ordered substream that can be processed in parallel with
  no cross-cell locking (the planetary-scale version of V2's per-twin locks).
- **Backpressure** — when processors fall behind, the stream buffers/throttles
  upstream rather than dropping data or stalling listeners. This is what lets V3
  absorb bursts of thousands of events per minute safely.
- **Batching & windowing** — coalescing a burst of events for one cell into a time/
  size window, so the estimator does one Update per window, not one per event.
- **Delivery semantics** — at-least-once with offsets, so a restart resumes rather
  than loses the world.

The interface is deliberately transport-agnostic: the first implementation is an
in-process async queue (great for tests and the single-node demo); the production
implementation is a set of **Kafka** topics/partitions. Callers — processors and the
estimator — depend only on the abstract ``Stream`` contract and never learn which is
behind it.

Status (Session 18): the abstract :class:`MessageBroker` plus an in-process
:class:`MemoryBroker` (default) and a :class:`RedisStreamBroker` adapter are live in
``broker.py``; :func:`get_broker` selects the backend from ``VECTIS_BROKER``.
"""

from __future__ import annotations

from vectis.realtime.streams.broker import (
    DEFAULT_TOPIC,
    MemoryBroker,
    MessageBroker,
    RedisStreamBroker,
    get_broker,
)
from vectis.realtime.streams.consumer import EventConsumer, Processor
from vectis.realtime.streams.producer import EventProducer

__all__ = [
    "DEFAULT_TOPIC",
    "EventConsumer",
    "EventProducer",
    "MemoryBroker",
    "MessageBroker",
    "Processor",
    "RedisStreamBroker",
    "get_broker",
]
