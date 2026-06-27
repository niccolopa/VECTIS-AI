"""WebSocket broadcaster — push "state changed" notifications to clients.

A minimal in-process fan-out: clients connect to the stream WebSocket, the
manager holds the live connections, and :meth:`ConnectionManager.broadcast`
pushes a JSON message to every one of them (dropping any that have gone away).

This is the **publish** half of the real-time loop and is deliberately the only
place that knows about WebSockets. To move to Redis/Kafka pub-sub later, replace
this class's transport (publish to a channel; a separate process relays to
sockets) — :class:`~vectis.streaming.updater.RealTimeUpdater` never imports it,
so the math is untouched.

``WebSocket`` is typed via :class:`typing.Protocol` so the manager is testable
with a plain fake and carries no hard Starlette dependency in its core logic.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from vectis.core.logging import get_logger

log = get_logger(__name__)


@runtime_checkable
class WebSocketLike(Protocol):
    """The slice of Starlette's ``WebSocket`` the broadcaster actually uses."""

    async def accept(self) -> None: ...
    async def send_json(self, data: Any) -> None: ...


class ConnectionManager:
    """Track live WebSocket connections and fan-out broadcasts to them."""

    def __init__(self) -> None:
        self._active: set[WebSocketLike] = set()

    @property
    def count(self) -> int:
        """Number of currently-connected clients."""
        return len(self._active)

    async def connect(self, websocket: WebSocketLike) -> None:
        """Accept the handshake and register the connection."""
        await websocket.accept()
        self._active.add(websocket)
        log.info("stream.ws_connect", clients=self.count)

    def disconnect(self, websocket: WebSocketLike) -> None:
        """Deregister a connection (idempotent)."""
        self._active.discard(websocket)
        log.info("stream.ws_disconnect", clients=self.count)

    async def broadcast(self, message: dict[str, Any]) -> int:
        """Send ``message`` to every connected client; drop dead sockets.

        Returns the number of clients the message reached. A failing ``send_json``
        means the peer is gone — it is removed rather than aborting the fan-out, so
        one stale connection can't block notifications to healthy ones.
        """
        delivered = 0
        for ws in list(self._active):
            try:
                await ws.send_json(message)
                delivered += 1
            except Exception:  # noqa: BLE001 — any send failure ⇒ drop the peer
                self.disconnect(ws)
        return delivered
