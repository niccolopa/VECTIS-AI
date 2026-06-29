"""Message broker — the central nervous system of V3.

The flow the broker sits in the middle of::

    Data Event  ->  [ Broker topic ]  ->  Processor  ->  State Update
    (ingestion)        publish/subscribe     consume

**Broker choice.** Three options were weighed against VECTIS's "clone & run"
constraint (the whole stack must boot offline, no infra, no keys):

- **Kafka** — the right answer at planetary scale (durable partitioned log, replay,
  consumer groups), but a ZooKeeper/KRaft cluster is far too heavy to require for a
  local dev checkout. Belongs in the production deployment, not the default path.
- **RabbitMQ** — solid AMQP routing, but a broker process is still a hard runtime
  dependency and its push model fits task queues better than an event-replay log.
- **Redis Streams** — a log-shaped stream (`XADD`/`XREADGROUP`/`XACK`) with consumer
  groups and at-least-once delivery, one lightweight process, trivial to run in Docker.
  The pragmatic production choice for V3's current scale.

So the design is an **abstract :class:`MessageBroker`** with two interchangeable backends:

- :class:`MemoryBroker` — an in-process ``asyncio.Queue`` per topic. Zero dependencies,
  the default; lets a developer exercise the entire ingestion→processing pipeline with
  nothing but the standard library.
- :class:`RedisStreamBroker` — a ``redis.asyncio`` adapter over Redis Streams, activated
  in production by setting ``VECTIS_BROKER=redis`` (``redis`` imported lazily so the
  default install never needs it).

Callers depend only on the abstract contract; :func:`get_broker` resolves the backend
from the environment, so swapping memory→Redis is a one-env-var change, no code edit.
"""

from __future__ import annotations

import asyncio
import os
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from vectis.core.logging import get_logger
from vectis.realtime.events.base import GlobalEvent

logger = get_logger(__name__)

#: Default topic the ingestion producer publishes onto.
DEFAULT_TOPIC = "vectis.events"


class MessageBroker(ABC):
    """Transport-agnostic publish/subscribe contract for :class:`GlobalEvent`s."""

    @abstractmethod
    async def publish(self, topic: str, event: GlobalEvent) -> None:
        """Append ``event`` to ``topic``."""
        ...

    @abstractmethod
    def subscribe(self, topic: str) -> AsyncIterator[GlobalEvent]:
        """Yield events from ``topic`` forever (an async iterator).

        Consumers should :meth:`ack` each event once processed; under at-least-once
        backends an un-acked event is redelivered after a restart.
        """
        ...

    async def ack(self, topic: str, event: GlobalEvent) -> None:
        """Acknowledge successful processing. No-op for in-memory transports."""
        return None

    async def close(self) -> None:
        return None


class MemoryBroker(MessageBroker):
    """Dependency-free broker backed by one :class:`asyncio.Queue` per topic.

    Delivery is in-process and single-consumer-per-topic (the local dev/test model).
    ``maxsize`` bounds a topic's buffer so a slow consumer applies natural backpressure
    on the producer instead of growing memory without limit.
    """

    def __init__(self, *, maxsize: int = 0) -> None:
        self._queues: dict[str, asyncio.Queue[GlobalEvent]] = {}
        self._maxsize = maxsize

    def _queue(self, topic: str) -> asyncio.Queue[GlobalEvent]:
        queue = self._queues.get(topic)
        if queue is None:
            queue = asyncio.Queue(maxsize=self._maxsize)
            self._queues[topic] = queue
        return queue

    async def publish(self, topic: str, event: GlobalEvent) -> None:
        await self._queue(topic).put(event)

    async def subscribe(self, topic: str) -> AsyncIterator[GlobalEvent]:
        queue = self._queue(topic)
        while True:
            event = await queue.get()
            try:
                yield event
            finally:
                queue.task_done()

    async def join(self, topic: str) -> None:
        """Block until every published event on ``topic`` has been consumed (tests)."""
        await self._queue(topic).join()


class RedisStreamBroker(MessageBroker):
    """Redis Streams adapter — production backend, activated via ``VECTIS_BROKER=redis``.

    Uses a consumer group for at-least-once delivery: ``XREADGROUP`` holds a message in
    the group's pending list until :meth:`ack` (``XACK``) confirms it, so a crashed
    consumer's in-flight events are redelivered rather than lost. ``redis`` is imported
    lazily, so this class only costs a dependency when actually used.

    ponytail: events deserialize to the *base* ``GlobalEvent`` (the concrete subclass and
    its ``to_observation`` hook don't survive the wire). The payload/variable are intact;
    re-typing belongs to the processor stage, which is where normalization lives anyway.
    """

    def __init__(
        self,
        url: str,
        *,
        group: str = "vectis",
        consumer: str | None = None,
        block_ms: int = 2000,
        redis_client: object | None = None,
    ) -> None:
        self._url = url
        self._group = group
        self._consumer = consumer or f"consumer-{os.getpid()}"
        self._block_ms = block_ms
        self._redis = redis_client
        self._groups_ready: set[str] = set()

    def _client(self) -> object:
        if self._redis is None:
            try:
                from redis.asyncio import Redis
            except ImportError as exc:  # pragma: no cover - exercised only without redis
                raise RuntimeError(
                    "RedisStreamBroker needs the 'redis' extra: pip install 'vectis[redis]'"
                ) from exc
            self._redis = Redis.from_url(self._url, decode_responses=True)
        return self._redis

    async def _ensure_group(self, topic: str) -> None:
        if topic in self._groups_ready:
            return
        client = self._client()
        try:
            await client.xgroup_create(topic, self._group, id="0", mkstream=True)  # type: ignore[attr-defined]
        except Exception as exc:  # BUSYGROUP: the group already exists — fine.
            if "BUSYGROUP" not in str(exc):
                raise
        self._groups_ready.add(topic)

    async def publish(self, topic: str, event: GlobalEvent) -> None:
        await self._client().xadd(topic, {"event": event.model_dump_json()})  # type: ignore[attr-defined]

    async def subscribe(self, topic: str) -> AsyncIterator[GlobalEvent]:
        await self._ensure_group(topic)
        client = self._client()
        while True:
            resp = await client.xreadgroup(  # type: ignore[attr-defined]
                self._group, self._consumer, {topic: ">"}, count=1, block=self._block_ms
            )
            if not resp:
                continue
            for _stream, messages in resp:
                for msg_id, fields in messages:
                    event = GlobalEvent.model_validate_json(fields["event"])
                    event.metadata["_stream_id"] = msg_id  # ack handle, carried in metadata
                    yield event

    async def ack(self, topic: str, event: GlobalEvent) -> None:
        msg_id = event.metadata.get("_stream_id")
        if msg_id is not None:
            await self._client().xack(topic, self._group, msg_id)  # type: ignore[attr-defined]

    async def close(self) -> None:
        if self._redis is not None:
            await self._redis.aclose()  # type: ignore[attr-defined]


def get_broker() -> MessageBroker:
    """Resolve the broker backend from the environment (``VECTIS_BROKER``).

    ``memory`` (default) → :class:`MemoryBroker`; ``redis`` → :class:`RedisStreamBroker`
    pointed at ``VECTIS_REDIS_URL`` (default ``redis://localhost:6379/0``).
    """
    backend = os.getenv("VECTIS_BROKER", "memory").lower()
    if backend == "redis":
        url = os.getenv("VECTIS_REDIS_URL", "redis://localhost:6379/0")
        logger.info("[INFO] using Redis Stream broker at %s", url)
        return RedisStreamBroker(url)
    logger.info("[INFO] using in-memory broker (set VECTIS_BROKER=redis for production)")
    return MemoryBroker()
