"""Consumer — drain the broker stream into a processor callback.

The downstream end of ``Data Event -> Queue -> Processor -> State Update``. A consumer
subscribes to a topic, hands each event to a ``processor`` callback, and **acks only on
success** — so a callback that raises does not ack, and under an at-least-once backend
(Redis Streams) the event is redelivered rather than silently dropped. A failing event
never takes down the loop: the error is logged and the consumer moves on.

The callback may be sync or async; the consumer awaits it if it returns an awaitable.
This is the seam the Session-19 ``StateEstimator`` plugs into: ``processor`` becomes
"validate → normalize → Update the cell state".
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from vectis.core.logging import get_logger
from vectis.realtime.events.base import GlobalEvent
from vectis.realtime.streams.broker import DEFAULT_TOPIC, MessageBroker

logger = get_logger(__name__)

#: A processor turns one event into a side effect (a state update). Sync or async.
Processor = Callable[[GlobalEvent], Awaitable[None] | None]


class EventConsumer:
    """Subscribe to a topic and route each event to a processor callback."""

    def __init__(
        self,
        broker: MessageBroker,
        processor: Processor,
        *,
        topic: str = DEFAULT_TOPIC,
    ) -> None:
        self._broker = broker
        self._processor = processor
        self._topic = topic
        self.processed = 0
        self.failed = 0

    async def _handle(self, event: GlobalEvent) -> bool:
        """Run the processor on one event; ack on success. Returns True if processed."""
        try:
            result = self._processor(event)
            if isinstance(result, Awaitable):
                await result
        except Exception:  # one bad event must not kill the stream
            self.failed += 1
            logger.exception("[ERROR] processor failed on event %s — not acking", event.event_id)
            return False
        await self._broker.ack(self._topic, event)
        self.processed += 1
        return True

    async def run(self, *, max_events: int | None = None) -> int:
        """Consume until ``max_events`` have been *seen* (processed or failed).

        Without ``max_events`` this runs forever. ``max_events`` bounds it for tests and
        finite batch drains. Returns the number successfully processed.
        """
        seen = 0
        async for event in self._broker.subscribe(self._topic):
            await self._handle(event)
            seen += 1
            if max_events is not None and seen >= max_events:
                break
        return self.processed
