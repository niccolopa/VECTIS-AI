"""Per-connector live-vs-synthetic status — the terminal's transparency source (Session 41).

The four planetary feeds each fall back to deterministic synthetic data when they can't
fetch live (see each connector, and the ``data_source`` stamped per-poll in Session 41).
This endpoint reports, per feed, which state it is in *right now*, plus the two aggregate
flags the UI needs: ``all_synthetic`` (the zero-credential fresh-clone case — one unmistakable
banner) and ``any_live``. It reads the connectors the shared ingestion loop already polls, so
the numbers reflect the real last poll — never a hardcoded assumption.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from vectis.realtime.events.base import DataSource
from vectis.realtime.live_stream import GlobalIngestionBroadcaster

router = APIRouter(prefix="/api/v1/connectors", tags=["connectors"])

#: Feed id → the short human hazard label the badge cluster shows.
_FEED_LABELS: dict[str, str] = {
    "nasa_firms": "Fire",
    "usgs_quake": "Quake",
    "gdacs": "Multi-hazard",
    "weather_api": "Weather",
}


class ConnectorStatus(BaseModel):
    source: str = Field(description="Stable feed id, e.g. 'nasa_firms'.")
    label: str = Field(description="Short human hazard label, e.g. 'Fire'.")
    data_source: DataSource = Field(description="Live or synthetic on the most recent poll.")


class ConnectorStatusResponse(BaseModel):
    connectors: list[ConnectorStatus]
    all_synthetic: bool = Field(
        description="True iff every feed is on synthetic fallback — the zero-credential "
        "fresh-clone state that warrants the single top-level 'full synthetic demo' banner."
    )
    any_live: bool


@router.get("", response_model=ConnectorStatusResponse)
def connector_status(request: Request) -> ConnectorStatusResponse:
    """Report each planetary feed's real live-vs-synthetic state from the last poll."""
    broadcaster: GlobalIngestionBroadcaster = request.app.state.global_ingestion
    statuses = [
        ConnectorStatus(
            source=c.source,
            label=_FEED_LABELS.get(c.source, c.source),
            data_source=c.last_data_source,
        )
        for c in broadcaster.connectors
    ]
    return ConnectorStatusResponse(
        connectors=statuses,
        all_synthetic=bool(statuses) and all(s.data_source == "synthetic_fallback" for s in statuses),
        any_live=any(s.data_source == "live" for s in statuses),
    )
