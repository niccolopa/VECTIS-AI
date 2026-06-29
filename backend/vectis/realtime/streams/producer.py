"""Producer — push ingested events onto the broker stream.

The first stage of ``Data Event -> Queue -> Processor -> State Update``. The
:class:`~vectis.realtime.ingestion.manager.IngestionManager` already polls every
connector into a merged list of :class:`GlobalEvent`s; the producer's only job is to
forward that list onto a broker topic so the processing side can consume it.

``IngestionManager.poll_once`` is synchronous (blocking HTTP under the hood), so each
poll runs in a worker thread via :func:`asyncio.to_thread` — the event loop is never
blocked while a slow feed is being fetched (the same off-loop pattern V2 streaming used).
"""

from __future__ import annotations

import asyncio

from vectis.core.logging import get_logger
from vectis.realtime.events.base import GlobalEvent
from vectis.realtime.ingestion.manager import IngestionManager
from vectis.realtime.streams.broker import DEFAULT_TOPIC, MessageBroker

logger = get_logger(__name__)


class EventProducer:
    """Forward events from an :class:`IngestionManager` onto a broker topic."""

    def __init__(
        self,
        manager: IngestionManager,
        broker: MessageBroker,
        *,
        topic: str = DEFAULT_TOPIC,
    ) -> None:
        self._manager = manager
        self._broker = broker
        self._topic = topic

    async def publish(self, events: list[GlobalEvent]) -> int:
        """Publish a batch of already-collected events; return the count published."""
        for event in events:
            await self._broker.publish(self._topic, event)
        return len(events)

    async def poll_and_publish(self) -> int:
        """Run one ingestion sweep (off the loop) and publish what it yields."""
        events = await asyncio.to_thread(self._manager.poll_once)
        published = await self.publish(events)
        logger.info("[INFO] producer published %d event(s) to '%s'", published, self._topic)
        return published

    async def run(self, *, interval: float = 60.0, max_cycles: int | None = None) -> int:
        """Poll-and-publish forever (or ``max_cycles`` times); return total published.

        Sleeps ``interval`` seconds *between* cycles, so the first batch goes out
        immediately. Bound it with ``max_cycles`` in tests and batch jobs.
        """
        total = 0
        cycle = 0
        while max_cycles is None or cycle < max_cycles:
            if cycle and interval:
                await asyncio.sleep(interval)
            total += await self.poll_and_publish()
            cycle += 1
        return total
