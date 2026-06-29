"""The continuous global state representation and the :class:`StateEstimator` ABC.

This is the heart of V3's "living system": a sparse field of per-cell beliefs over a
world grid, kept current by a streaming **predict–correct** filter that folds each
:class:`~vectis.realtime.events.base.GlobalObservation` in incrementally — never
replaying history, never recomputing from scratch.

Two schemas + one interface:
- :class:`CellState` — one cell's belief: a mean vector of variables **and the
  covariance around them** (so uncertainty is first-class), plus the reused V2 discrete
  scenario posterior.
- :class:`GlobalState` — the sparse registry of active cells (only places with recent
  data are materialized).
- :class:`StateEstimator` — the continuous-stream Update engine. Concrete subclasses
  implement the Kalman filter (continuous variables) and delegate the discrete scenario
  belief to the existing V2 Bayesian updater.

Pure ``numpy``/``scipy`` math at implementation time; like all of the simulation layer
this never imports the agents/LLM layer — the Math Firewall holds at global scale.
Design notes: ``docs/v3_state_management.md``.

Status: **blueprint** (Session 16) — contracts only, no filter logic. The first
concrete Kalman :class:`StateEstimator` lands in Session 17.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from datetime import UTC, datetime

from pydantic import BaseModel, Field

from vectis.realtime.events.base import CellId, GlobalObservation
from vectis.simulation.schemas import ScenarioSet


def _utcnow() -> datetime:
    return datetime.now(UTC)


class CellState(BaseModel):
    """The current belief about one grid cell — a distribution, not a point.

    ``mean`` and ``covariance`` are keyed by canonical ``WorldState`` variable name so
    the representation is self-describing and sparse (a cell only tracks the variables
    it has seen). ``covariance`` is the symmetric variable×variable matrix encoded as a
    nested mapping; its diagonal is each variable's variance (uncertainty), off-diagonal
    the cross-correlations a Kalman filter maintains.
    """

    cell: CellId
    mean: dict[str, float] = Field(
        default_factory=dict, description="Best current estimate per variable."
    )
    covariance: dict[str, dict[str, float]] = Field(
        default_factory=dict, description="Uncertainty + cross-correlation per variable pair."
    )
    scenario_belief: ScenarioSet | None = Field(
        default=None, description="Reused V2 discrete posterior over scenarios for this cell."
    )
    updated_at: datetime = Field(default_factory=_utcnow)
    sources: list[str] = Field(
        default_factory=list, description="Feeds that have shaped this estimate (provenance)."
    )


class GlobalState(BaseModel):
    """A sparse snapshot of every active cell's state.

    Only cells with recent observations are present; quiet cells age out to the
    persisted tier (see ``docs/v3_state_management.md``). Memory tracks *activity*, not
    planetary area. This mirrors the V2 ``StateManager`` registry, keyed by
    :data:`CellId` instead of a single region string and backed by a hot/cold store.
    """

    cells: dict[CellId, CellState] = Field(default_factory=dict)
    as_of: datetime = Field(default_factory=_utcnow)


class StateEstimator(ABC):
    """Continuously estimate the world's state from a stream of observations.

    The V3 generalization of V2's on-demand Bayesian update into an always-on,
    per-cell **predict–correct** loop designed to be fed by a stream — one observation,
    or a batched window, at a time. Every method operates on a single cell so the
    estimator shards cleanly across the global grid (no cross-cell locking), which is
    what lets it absorb thousands of events per minute.

    Implementations are expected to:
    - keep Updates **incremental and O(1)** per observation (no history replay);
    - carry **covariance**, so forecasts can be drawn from the state *distribution*;
    - delegate the discrete scenario belief to the V2 ``BayesianUpdater``.
    """

    #: Stable identifier used in estimate provenance/auditing.
    name: str = "state_estimator"

    @abstractmethod
    def update(self, observation: GlobalObservation) -> CellState:
        """Fold one observation into the addressed cell and return its new state.

        The core continuous step: **predict** the cell's prior forward to
        ``observation.observed_at`` (dynamics + covariance growth), then **correct** it
        with the observation weighted by their relative uncertainties (Kalman gain).
        Mutates the live :class:`GlobalState`; constant-time in the event history.
        """
        raise NotImplementedError

    def update_batch(self, observations: Iterable[GlobalObservation]) -> list[CellState]:
        """Fold a window of observations in order, returning each resulting state.

        Default: apply :meth:`update` sequentially. Implementations may override to
        fuse same-cell observations in one correction step — the scale lever that keeps
        the Update rate bounded under bursty streams. Concrete fusion logic is S17+.
        """
        return [self.update(obs) for obs in observations]

    @abstractmethod
    def predict(self, cell: CellId, at: datetime) -> CellState | None:
        """Evolve a cell's estimate forward to time ``at`` *without* an observation.

        The standalone predict step — used by forecasting to read the state at "now"
        (or a future instant) with covariance grown for the elapsed time. ``None`` if
        the cell is not currently tracked.
        """
        raise NotImplementedError

    @abstractmethod
    def get(self, cell: CellId) -> CellState | None:
        """Return a cell's current estimate without advancing it (``None`` if absent)."""
        raise NotImplementedError

    @property
    @abstractmethod
    def active_cells(self) -> int:
        """Number of cells currently materialized in the hot tier."""
        raise NotImplementedError
