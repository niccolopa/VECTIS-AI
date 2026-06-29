"""Session 18 — event streaming engine: broker, producer, consumer.

Async behaviour is driven through ``asyncio.run`` inside plain sync tests (the same
dependency-free pattern as ``tests/streaming/test_realtime.py``) — no asyncio plugin.
"""

from __future__ import annotations

import asyncio

from vectis.realtime.connectors.base import BaseAPIConnector
from vectis.realtime.events.base import GeoPoint, GlobalEvent
from vectis.realtime.ingestion.manager import IngestionManager
from vectis.realtime.streams.broker import MemoryBroker
from vectis.realtime.streams.consumer import EventConsumer
from vectis.realtime.streams.producer import EventProducer


def _event(i: int) -> GlobalEvent:
    return GlobalEvent(source="test", location=GeoPoint(lat=0, lon=0), payload={"i": i})


class _BurstConnector(BaseAPIConnector):
    """A connector that emits ``n`` synthetic events per collect (no network)."""

    source = "burst"

    def __init__(self, n: int) -> None:
        super().__init__()
        self._n = n

    def fetch(self) -> int:
        return self._n

    def normalize(self, raw: int) -> list[GlobalEvent]:
        return [_event(i) for i in range(raw)]


def test_memory_broker_enqueues_and_dequeues() -> None:
    """Published events come back out of subscribe in order."""

    async def scenario() -> list[int]:
        broker = MemoryBroker()
        for i in range(3):
            await broker.publish("t", _event(i))

        out: list[int] = []
        async for event in broker.subscribe("t"):
            out.append(event.payload["i"])
            if len(out) == 3:
                break
        return out

    assert asyncio.run(scenario()) == [0, 1, 2]


def test_producer_to_consumer_delivers_all_100() -> None:
    """100 events produced from the IngestionManager are all processed by the consumer."""

    async def scenario() -> int:
        broker = MemoryBroker()
        manager = IngestionManager([_BurstConnector(100)])
        producer = EventProducer(manager, broker, topic="t")
        seen: list[GlobalEvent] = []
        consumer = EventConsumer(broker, seen.append, topic="t")

        published = await producer.poll_and_publish()
        assert published == 100

        processed = await consumer.run(max_events=100)
        assert len(seen) == 100
        return processed

    assert asyncio.run(scenario()) == 100


def test_consumer_survives_a_failing_event() -> None:
    """A processor raising on one event is logged and skipped, not fatal; rest succeed."""

    async def scenario() -> tuple[int, int]:
        broker = MemoryBroker()
        for i in range(5):
            await broker.publish("t", _event(i))

        def processor(event: GlobalEvent) -> None:
            if event.payload["i"] == 2:
                raise ValueError("boom")

        consumer = EventConsumer(broker, processor, topic="t")
        await consumer.run(max_events=5)
        return consumer.processed, consumer.failed

    assert asyncio.run(scenario()) == (4, 1)


def test_consumer_awaits_async_processor() -> None:
    """An async processor callback is awaited, not left as an un-awaited coroutine."""

    async def scenario() -> int:
        broker = MemoryBroker()
        await broker.publish("t", _event(0))
        hits: list[int] = []

        async def processor(event: GlobalEvent) -> None:
            await asyncio.sleep(0)
            hits.append(event.payload["i"])

        consumer = EventConsumer(broker, processor, topic="t")
        await consumer.run(max_events=1)
        return len(hits)

    assert asyncio.run(scenario()) == 1
