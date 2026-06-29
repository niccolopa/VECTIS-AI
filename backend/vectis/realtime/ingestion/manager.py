"""Ingestion orchestrator — fan multiple connectors into one event stream.

The :class:`BaseAPIConnector` already makes a single feed resilient (retry + graceful
degradation). The manager's only job is to hold a set of active connectors, poll them,
and yield a steady, merged stream of :class:`GlobalEvent`s — so a dead feed simply
contributes nothing to a cycle instead of stalling the others.

Two entry points:

- :meth:`poll_once` — one synchronous sweep across all connectors (a scheduler tick).
- :meth:`run` — a self-pacing generator that polls forever (or ``max_cycles`` times),
  sleeping ``interval`` seconds between sweeps. The steady stream the brief asks for.

Kept synchronous on purpose: the connectors are I/O-bound but each ``collect()`` is
already isolated, and a generator is the simplest thing that delivers a continuous
stream. ponytail: swap the loop for an asyncio gather / Kafka producer in Session 18
when stream processing & routing lands — the connector contract stays the same.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator

from vectis.core.logging import get_logger
from vectis.realtime.connectors.base import BaseAPIConnector
from vectis.realtime.events.base import GlobalEvent

logger = get_logger(__name__)


class IngestionManager:
    """Manage active connectors and yield their merged :class:`GlobalEvent` stream."""

    def __init__(
        self,
        connectors: list[BaseAPIConnector] | None = None,
        *,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._connectors: list[BaseAPIConnector] = list(connectors or [])
        self._sleep = sleep  # injectable so a polling loop is testable without real waits

    def register(self, connector: BaseAPIConnector) -> None:
        """Add a connector to the active set."""
        self._connectors.append(connector)

    @property
    def connectors(self) -> list[BaseAPIConnector]:
        return list(self._connectors)

    def poll_once(self) -> list[GlobalEvent]:
        """Collect events from every connector once, merged into one list.

        Each ``collect()`` swallows its own outage and returns ``[]``, so one dead feed
        never aborts the sweep — the others still report.
        """
        events: list[GlobalEvent] = []
        for connector in self._connectors:
            events.extend(connector.collect())
        logger.info("[INFO] ingestion cycle yielded %d event(s) from %d connector(s)",
                    len(events), len(self._connectors))
        return events

    def run(self, *, interval: float = 60.0, max_cycles: int | None = None) -> Iterator[GlobalEvent]:
        """Yield a continuous stream of events, polling every ``interval`` seconds.

        Runs forever by default; pass ``max_cycles`` to bound it (tests, batch jobs).
        Sleeps *between* cycles only, so the first batch is available immediately.
        """
        cycle = 0
        while max_cycles is None or cycle < max_cycles:
            if cycle and interval:
                self._sleep(interval)
            yield from self.poll_once()
            cycle += 1

    def close(self) -> None:
        for connector in self._connectors:
            connector.close()
