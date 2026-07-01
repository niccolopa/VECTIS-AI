"""The canonical global ingestion wiring — every live planetary feed in one manager.

Session 31 turns the single-region V3 ingestion into a genuinely worldwide one. This module
is the entry point: it registers the four real feeds — Open-Meteo weather, NASA FIRMS fires,
USGS earthquakes, GDACS multi-hazard alerts — into one :class:`IngestionManager`, so a poll
cycle yields :class:`GlobalEvent`s spread across the planet, each at its real ``(lat, lon)``.

Every connector is offline-safe (see each module), so :func:`build_global_ingestion_manager`
runs on a fresh clone with zero keys and zero network: it streams synthetic-but-plausible
global events instead of crashing. Set the keys / point at the Sluice and the same manager
streams real detections onto the H3 cells where they actually occurred.

The events carry a :class:`GeoPoint`; ``event.to_observation()`` routes each through
:func:`~vectis.realtime.state.cell_id.assign_cell_id`, so a California fire and a Japan quake
land on different cells with no extra wiring. :func:`ingest_into` is the convenience loop that
folds a poll cycle straight into a state store for callers that just want cells populated.
"""

from __future__ import annotations

from collections.abc import Iterable

from vectis.core.logging import get_logger
from vectis.realtime.connectors.base import BaseAPIConnector
from vectis.realtime.connectors.firms import FirmsConnector
from vectis.realtime.connectors.gdacs import GdacsConnector
from vectis.realtime.connectors.usgs import UsgsQuakeConnector
from vectis.realtime.connectors.weather import WeatherAPIConnector
from vectis.realtime.events.base import GlobalEvent
from vectis.realtime.ingestion.manager import IngestionManager
from vectis.realtime.state.models import WorldCellState
from vectis.realtime.state.store import StateStore
from vectis.realtime.state.updater import StateUpdater

logger = get_logger(__name__)


def default_global_connectors() -> list[BaseAPIConnector]:
    """The four real worldwide feeds, each offline-safe by default."""
    return [
        WeatherAPIConnector(),
        FirmsConnector(),
        UsgsQuakeConnector(),
        GdacsConnector(),
    ]


def build_global_ingestion_manager(
    connectors: Iterable[BaseAPIConnector] | None = None,
) -> IngestionManager:
    """Assemble the global :class:`IngestionManager`.

    Defaults to all four real feeds; pass ``connectors`` to inject offline/mocked ones
    (tests, deterministic runs). Because each ``collect()`` swallows its own outage, one
    dead feed contributes nothing to a cycle while the other three keep flowing.
    """
    return IngestionManager(list(connectors or default_global_connectors()))


def ingest_into(
    manager: IngestionManager, store: StateStore[WorldCellState]
) -> list[GlobalEvent]:
    """Poll every feed once and fold each event into ``store`` at its real H3 cell.

    Returns the raw events polled (for inspection). The store ends up with one live cell per
    distinct location observed this cycle — the sparse global active set Session 30 built.
    """
    updater = StateUpdater(store)
    events = manager.poll_once()
    for event in events:
        updater.apply_observation(event.to_observation())
    return events


def demo() -> None:
    """Self-check: the default global manager registers all four real feed sources."""
    sources = {c.source for c in build_global_ingestion_manager().connectors}
    assert sources == {"weather_api", "nasa_firms", "usgs_quake", "gdacs"}, sources
    print("OK", sorted(sources))


if __name__ == "__main__":
    demo()
