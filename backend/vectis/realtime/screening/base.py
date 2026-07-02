"""The screening layer — a near-free, per-hazard risk index over the active cell set.

VECTIS runs two independent risk code paths that must never be confused:

- **Screening (this module, Tier 0)** — a single vectorized point-estimate per active
  cell on every state update. No sampling, no scenarios, no Monte Carlo. This is what the
  global heat map renders, at essentially zero marginal cost, over *every* active cell.
- **Simulation (the V2 engine)** — the expensive Monte Carlo + Bayesian + decision-board
  pipeline that only ever runs on the small subset of cells a future session *promotes*.

A :class:`ScreeningIndex` is the pluggable, **per-hazard** contract for the cheap path,
mirroring how a :class:`~vectis.simulation.models.wildfire.HazardModel` plugs into the
Monte Carlo engine. Indices live in a registry keyed by hazard name, so a future session
adds a flood or seismic screen by registering a new implementation — **without touching
this module**.

Honest scope (read this before adding a hazard to the heat map)
---------------------------------------------------------------
``wildfire`` (:mod:`.wildfire`, Session 32) and — since Session 35 — ``flood`` / ``quake``
/ ``cyclone`` (:mod:`.multi_hazard`) have real implementations, each wrapping its hazard
model's **illustrative, uncalibrated coefficients** (a score existing is not validation).
The remaining observed hazards — tsunami, volcano — **still have no risk model**: they are
listed in :data:`UNSCREENED_HAZARDS` and have **no registry entry**, so the sweep returns
*nothing* for them rather than a fabricated number. :class:`NotYetScreenedIndex` is the
explicit stub/extension point: it documents the gap and raises if scored, so a fake index
can never silently ship a plausible-looking value.

Pure arithmetic, no LLM, no simulation import — the Math Firewall holds.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from typing import NamedTuple

from vectis.core.schemas import RiskBand
from vectis.realtime.events.base import CellId
from vectis.realtime.state.models import WorldCellState

#: Hazards observed in the Session-31 event stream that have **no** screening model yet.
#: They are deliberately absent from the registry — a screen for them is a future session.
#: (Session 35 graduated quake / flood / cyclone out of this set into real indexes.)
UNSCREENED_HAZARDS: frozenset[str] = frozenset({"tsunami", "volcano"})


class ScreeningScore(NamedTuple):
    """One cell's cheap risk index for one hazard, on the shared 0–100 VECTIS scale.

    A ``NamedTuple`` (not a dataclass) so 100k of them construct fast in a sweep — this is
    the per-cell result object the whole heat map is made of.
    """

    hazard: str
    value: float  # 0–100, same convention as core RiskBand / the full engine's risk_score

    @property
    def band(self) -> RiskBand:
        """Bucket the score with the project-wide :class:`RiskBand` thresholds."""
        return RiskBand.from_score(self.value)


class ScreeningIndex(ABC):
    """A vectorized, single-pass risk index for one hazard over a batch of active cells."""

    #: Hazard this index screens (its registry key). Set by each concrete subclass.
    hazard: str

    @abstractmethod
    def score(self, cells: Sequence[WorldCellState]) -> dict[CellId, ScreeningScore]:
        """Score every cell that carries the state this hazard needs.

        Vectorized: one array pass over the batch, never a per-cell Python loop over the
        math. Cells lacking the relevant state are **skipped** (absent from the result),
        never crashed and never given a fabricated neutral number.
        """
        raise NotImplementedError


class NotYetScreenedIndex(ScreeningIndex):
    """Explicit, honest placeholder for a hazard with no model yet.

    Not registered by default — it exists so a future session sees the extension point and
    so the "no fake numbers" rule is *enforced*: scoring an unmodelled hazard raises instead
    of returning a plausible value. Register a real :class:`ScreeningIndex` to replace it.
    """

    def __init__(self, hazard: str) -> None:
        self.hazard = hazard

    def score(self, cells: Sequence[WorldCellState]) -> dict[CellId, ScreeningScore]:
        raise NotImplementedError(
            f"hazard {self.hazard!r} has no screening model yet — "
            "register a real ScreeningIndex before adding it to the heat map"
        )


# ── registry ─────────────────────────────────────────────────────────────────────────
# Keyed by hazard name; a future session extends the heat map by registering here, never by
# editing the sweep. Populated at import: concrete indices call register() in their modules.
_REGISTRY: dict[str, ScreeningIndex] = {}


def register(index: ScreeningIndex) -> ScreeningIndex:
    """Register ``index`` under its :attr:`~ScreeningIndex.hazard` key (returns it)."""
    if not getattr(index, "hazard", None):
        raise ValueError("a ScreeningIndex must set a non-empty `hazard` before registering")
    _REGISTRY[index.hazard] = index
    return index


def default_registry() -> Mapping[str, ScreeningIndex]:
    """A snapshot of the registered ``{hazard: ScreeningIndex}`` — wildfire only, today."""
    return dict(_REGISTRY)
