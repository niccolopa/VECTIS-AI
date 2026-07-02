"""Tier 0 screening — the cheap, per-hazard global risk index (Session 32).

Importing this package registers every available :class:`ScreeningIndex` into the shared
registry (wildfire, flood, quake, cyclone), so :func:`default_registry` and
:class:`~vectis.realtime.screening.sweep.GlobalScreeningSweep` see them.
"""

from __future__ import annotations

from vectis.realtime.screening.base import (
    UNSCREENED_HAZARDS,
    NotYetScreenedIndex,
    ScreeningIndex,
    ScreeningScore,
    default_registry,
    register,
)
from vectis.realtime.screening.multi_hazard import (  # registers flood/quake/cyclone
    CycloneScreeningIndex,
    EarthquakeScreeningIndex,
    FloodScreeningIndex,
)
from vectis.realtime.screening.sweep import GlobalScreeningSweep
from vectis.realtime.screening.wildfire import WildfireScreeningIndex  # registers wildfire

__all__ = [
    "UNSCREENED_HAZARDS",
    "CycloneScreeningIndex",
    "EarthquakeScreeningIndex",
    "FloodScreeningIndex",
    "GlobalScreeningSweep",
    "NotYetScreenedIndex",
    "ScreeningIndex",
    "ScreeningScore",
    "WildfireScreeningIndex",
    "default_registry",
    "register",
]
