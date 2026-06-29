"""Generic JSON connector — ingest arbitrary payloads (e.g. webhooks).

Configurable field mapping turns any flat-or-nested JSON record into V3 events without
a bespoke connector. Two entry points:

- :meth:`fetch` + :meth:`normalize` — poll a JSON endpoint like the other connectors.
- :meth:`ingest` — normalize a payload pushed *to* us (a webhook), bypassing HTTP.
"""

from __future__ import annotations

from typing import Any

from vectis.realtime.connectors.base import BaseAPIConnector
from vectis.realtime.events.base import GeoPoint, GlobalEvent, GlobalObservation, naive_cell_id


class GenericEvent(GlobalEvent):
    """An event from an arbitrary mapped JSON record."""

    def to_observation(self) -> GlobalObservation:
        return GlobalObservation(
            cell_id=self.cell_id or naive_cell_id(self.location),
            variable=self.payload["variable"],
            value=float(self.payload["value"]),
            std=self.payload.get("std"),
            observed_at=self.observed_at,
            source=self.source,
        )


class GenericJSONConnector(BaseAPIConnector):
    """Map records from an arbitrary JSON feed/webhook to canonical events.

    ``records_key`` locates the list of records in the payload (``None`` = the payload
    *is* the list, or a single record). ``lat_field``/``lon_field``/``value_field`` name
    the coordinate and value keys; ``variable`` is the canonical WorldState variable the
    value maps to.
    """

    def __init__(
        self,
        *,
        source: str = "generic_json",
        variable: str,
        value_field: str = "value",
        lat_field: str = "lat",
        lon_field: str = "lon",
        records_key: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.source = source
        self.variable = variable
        self.value_field = value_field
        self.lat_field = lat_field
        self.lon_field = lon_field
        self.records_key = records_key

    def fetch(self) -> Any:
        if not self.base_url:
            return []  # nothing to poll; this connector is usually push-driven
        return self.get_json(self.base_url)

    def _records(self, raw: Any) -> list[dict[str, Any]]:
        if self.records_key is not None:
            raw = raw.get(self.records_key, [])
        if isinstance(raw, dict):
            return [raw]
        return list(raw)

    def normalize(self, raw: Any) -> list[GlobalEvent]:
        events: list[GlobalEvent] = []
        for rec in self._records(raw):
            events.append(
                GenericEvent(
                    source=self.source,
                    location=GeoPoint(lat=float(rec[self.lat_field]), lon=float(rec[self.lon_field])),
                    payload={"variable": self.variable, "value": float(rec[self.value_field])},
                )
            )
        return events

    def ingest(self, payload: Any) -> list[GlobalEvent]:
        """Normalize a pushed payload (webhook) without an HTTP round-trip."""
        return self.normalize(payload)
