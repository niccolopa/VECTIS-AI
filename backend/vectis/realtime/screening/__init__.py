"""Tier 0 screening — the cheap, per-hazard global risk index (Session 32).

Importing this package registers every available :class:`ScreeningIndex` into the shared
registry (wildfire only, today), so :func:`default_registry` and
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

__all__ = [
    "UNSCREENED_HAZARDS",
    "NotYetScreenedIndex",
    "ScreeningIndex",
    "ScreeningScore",
    "default_registry",
    "register",
]
