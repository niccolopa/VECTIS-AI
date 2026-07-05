"""Foundational V3 event schemas — the global wire format.

Two schemas, on either side of the trust boundary:

- :class:`GlobalEvent` — *raw, untrusted* data as it leaves an external source. The
  V3 generalization of the V2 ``StreamEvent``: instead of a single ``region: str`` it
  carries **global geospatial scope** (a :class:`GeoPoint` and, once assigned, the
  grid :data:`CellId` it falls in) plus full provenance and an opaque payload.
- :class:`GlobalObservation` — an Event after a processor has validated, deduplicated,
  and normalized it: a single canonical measurement, tied to a grid cell, ready for
  the :class:`~vectis.realtime.state.base.StateEstimator`. This is the clean line
  between *transport* (Event) and *math* (Observation), lifted to global scope.

Pure, picklable Pydantic models with no behavior beyond a translation hook — so the
same payload flows through an in-process stub today and a Kafka topic tomorrow
unchanged. No computation, no LLM.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

#: Whether an event carries genuinely-fetched live data or a connector's offline synthetic
#: fallback. Stamped per-poll by the connector (Session 41) so live-vs-synthetic status
#: propagates from ingestion all the way to the terminal — never a silent substitution.
DataSource = Literal["live", "synthetic_fallback"]

#: A grid-cell identifier (e.g. an H3 index or a raster tile key). The exact tiling is
#: a ``state/`` implementation detail; the rest of V3 treats a cell as an opaque,
#: shardable key. ``None`` on a raw event until a processor assigns it.
CellId = str


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _event_id() -> str:
    return uuid.uuid4().hex


class GeoPoint(BaseModel):
    """A point on Earth in decimal degrees (WGS84). Global scope made explicit."""

    lat: float = Field(ge=-90.0, le=90.0, description="Latitude, −90…90.")
    lon: float = Field(ge=-180.0, le=180.0, description="Longitude, −180…180.")


class GlobalEvent(BaseModel):
    """Raw, untrusted data from a real-time source — the edge type of V3.

    Concrete sources (FIRMS, ERA5, IoT…) subclass this and add their native fields,
    then implement :meth:`to_observation` to translate themselves into the canonical
    :class:`GlobalObservation` the math layer speaks. The base makes no claim about the
    payload's correctness — validation/normalization happen in the processor stage.
    """

    event_id: str = Field(default_factory=_event_id)
    source: str = Field(description="Originating feed/connector id, e.g. 'nasa_firms'.")
    location: GeoPoint = Field(description="Where on Earth this event was measured.")
    cell_id: CellId | None = Field(
        default=None, description="Grid cell the location maps to (assigned by a processor)."
    )
    observed_at: datetime = Field(
        default_factory=_utcnow, description="When the source measured the value."
    )
    ingested_at: datetime = Field(
        default_factory=_utcnow, description="When VECTIS received the event."
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Raw source confidence in this measurement, 0…1 (1 = fully trusted).",
    )
    data_source: DataSource = Field(
        default="synthetic_fallback",
        description="Whether this event is genuinely-fetched live data or a connector's "
        "offline synthetic fallback. Stamped per-poll; defaults to the honest, safe "
        "assumption (synthetic) until a connector confirms a live fetch.",
    )
    payload: dict[str, Any] = Field(
        default_factory=dict, description="Raw, source-specific fields (untrusted)."
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Free-form provenance/traceability (request id, feed url, tile…).",
    )

    def to_observation(self) -> GlobalObservation:
        """Translate this raw event into a canonical :class:`GlobalObservation`.

        Implemented by each concrete source event. Kept as a hook (not an
        ``@abstractmethod``) because Pydantic models and ABCs compose awkwardly — the
        same pattern the V2 ``StreamEvent`` uses.
        """
        raise NotImplementedError


class GlobalObservation(BaseModel):
    """A validated, normalized measurement tied to a grid cell — ready for the estimator.

    The V2 ``Observation`` (variable · value · std) lifted to global scope: it adds the
    :data:`CellId` it belongs to and the provenance needed to make an Update auditable.
    One canonical measurement of one ``WorldState`` variable; a processor emits these
    from raw events, deduplicated and unit-normalized.
    """

    cell_id: CellId = Field(description="Grid cell this observation updates.")
    variable: str = Field(description="Canonical WorldState variable name.")
    value: float
    std: float | None = Field(
        default=None, ge=0.0, description="Measurement uncertainty (1σ), if known."
    )
    observed_at: datetime = Field(default_factory=_utcnow)
    source: str = Field(description="Originating feed id, carried through for provenance.")
