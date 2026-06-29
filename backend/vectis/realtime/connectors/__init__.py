"""Source connectors — the edge of V3 that turns the real world into events.

Each connector ``fetch()``es raw JSON from an external feed and ``normalize()``s it
into :class:`~vectis.realtime.events.base.GlobalEvent` objects. The
:class:`~vectis.realtime.connectors.base.BaseAPIConnector` handles the messy parts
once — timeouts, connection drops, transient 5xx, exponential backoff — so concrete
connectors only describe *their* feed's shape.

Connectors run **offline by default**: with no ``base_url`` configured each emits a
deterministic synthetic payload, so the whole ingestion layer (and CI) works with no
network and no credentials — VECTIS's iron rule.
"""

from __future__ import annotations

from vectis.realtime.connectors.base import BaseAPIConnector, ConnectorError

__all__ = ["BaseAPIConnector", "ConnectorError"]
