"""StateUpdater — fold a normalized observation into a cell's present state.

This is the concrete fulfilment of the Session-16 ``StateEstimator`` role: the consumer
end of ``Data Event → Queue → Processor → State Update``. It is the seam the streaming
:class:`~vectis.realtime.streams.consumer.EventConsumer` plugs into — its ``processor``
callback becomes "normalize → :meth:`apply_observation`".

Per the Session-19 brief the merge is a simple **exponential moving average** (the first
reading of a variable sets it directly; later readings blend toward the new value), with
**version + timestamp** bumped on every applied observation. The prior version is
preserved in the store's history, so every transition is auditable and replayable.

# ponytail: EMA, not a Kalman gain — no covariance yet. Swap the merge for the
# predict–correct filter (base.StateEstimator) once per-variable uncertainty is tracked.
Pure arithmetic, no LLM — the Math Firewall holds.
"""

from __future__ import annotations

from datetime import UTC, datetime

from vectis.core.logging import get_logger
from vectis.realtime.events.base import GlobalObservation
from vectis.realtime.state.models import WorldCellState
from vectis.realtime.state.store import StateStore

logger = get_logger(__name__)

#: Canonical / intuitive variable names → the concrete state field they update.
#: Covers the connectors' canonical names (e.g. ``temp_anomaly_c``) and plain aliases.
VARIABLE_FIELDS: dict[str, str] = {
    "temperature": "temperature",
    "temp": "temperature",
    "temp_anomaly_c": "temperature",
    "humidity": "humidity",
    "humidity_pct": "humidity",
    "drought_index": "drought_index",
    "drought": "drought_index",
    "fire_risk": "fire_risk",
    "fire": "fire_risk",
    # Multi-hazard variables the Session-31 real feeds emit (Session 35): structured
    # fields the flood / earthquake / cyclone models read, no longer parked in `extra`.
    "precipitation_mm": "precipitation_mm",
    "precipitation": "precipitation_mm",
    "earthquake_magnitude": "earthquake_magnitude",
    "flood_alert_level": "flood_alert_level",
    "cyclone_alert_level": "cyclone_alert_level",
}

#: Fields carrying the *latest reported event truth* (a magnitude, an alert ordinal) —
#: overwritten, never EMA-blended: averaging a new M7 with an old M5 would fabricate an M6.
LATEST_VALUE_FIELDS: frozenset[str] = frozenset(
    {"earthquake_magnitude", "flood_alert_level", "cyclone_alert_level"}
)


class StateUpdater:
    """Merge incoming observations into per-cell state, versioning every transition.

    Stateless apart from its ``store`` and the EMA weight ``alpha``: all state lives in
    the :class:`StateStore`, so the updater shards trivially across cells.
    """

    def __init__(self, store: StateStore[WorldCellState], *, alpha: float = 0.5) -> None:
        if not 0.0 < alpha <= 1.0:
            raise ValueError("alpha must be in (0, 1]")
        self._store = store
        self._alpha = alpha

    def apply_observation(self, observation: GlobalObservation) -> WorldCellState:
        """Fold one observation into its cell and return the new versioned state.

        Fetch current → EMA-merge the observed variable → bump version + timestamp →
        save (the prior version drops into history). Idempotent in shape: a never-seen
        cell is created at version 1; ``alpha=1.0`` makes the merge a direct overwrite.
        """
        current = self._store.get_state(observation.cell_id)
        if current is None:
            current = WorldCellState(cell_id=observation.cell_id)

        # Build the next version (copy so the stored prior stays immutable in history).
        new_state = current.model_copy(deep=True)
        self._merge(new_state, observation)

        new_state.version = current.version + 1
        new_state.last_updated = datetime.now(UTC)
        if observation.source and observation.source not in new_state.sources:
            new_state.sources.append(observation.source)

        self._store.save_state(new_state)
        return new_state

    def _merge(self, state: WorldCellState, observation: GlobalObservation) -> None:
        """EMA-blend the observed variable into the right field (or ``extra``)."""
        field = VARIABLE_FIELDS.get(observation.variable)
        if field is None:
            # Unknown but valid measurement — keep it rather than drop it.
            prior = state.extra.get(observation.variable)
            state.extra[observation.variable] = self._ema(prior, observation.value)
            return
        if field in LATEST_VALUE_FIELDS:
            setattr(state, field, observation.value)
            return
        prior = getattr(state, field)
        setattr(state, field, self._ema(prior, observation.value))

    def _ema(self, prior: float | None, value: float) -> float:
        """First reading sets the value; later readings blend toward it."""
        if prior is None:
            return value
        return self._alpha * value + (1.0 - self._alpha) * prior
