"""KalmanStateUpdater — fold observations into per-cell beliefs via predict→correct.

The Session-20 replacement for the EMA :class:`~vectis.realtime.state.updater.StateUpdater`.
Same seam (the streaming consumer's ``processor`` callback) and same versioned store, but
the merge is now a 1D Kalman step instead of a fixed-weight average:

1. **predict** the variable's prior belief forward to ``observation.observed_at`` —
   variance grows by ``process_noise_rate × seconds_elapsed`` (a stale estimate becomes
   less certain, so it defers more to fresh data);
2. derive the **observation variance** from the measurement's own uncertainty
   (``observation.std²``, the carrier of the source ``GlobalEvent.confidence``), or a
   configured default;
3. **correct** the prediction with the observation, weighted by the Kalman gain;
4. save the new ``(mean, variance)`` and bump version/timestamp (prior drops into history).

Because correction shrinks variance, a run of consistent observations makes the cell
*measurably more confident* over time — the property the EMA could never give.

Pure arithmetic, no LLM — the Math Firewall holds.
"""

from __future__ import annotations

from vectis.core.logging import get_logger
from vectis.realtime.events.base import GlobalObservation
from vectis.realtime.forecasting.kalman.filter import Gaussian, correct, predict
from vectis.realtime.forecasting.kalman.state_model import KalmanCellState, VariableEstimate
from vectis.realtime.state.store import StateStore
from vectis.realtime.state.updater import VARIABLE_FIELDS

logger = get_logger(__name__)


class KalmanStateUpdater:
    """Merge observations into per-cell Gaussian state, versioning every transition.

    Stateless apart from its ``store`` and a few tuning constants, so it shards across
    cells exactly like the EMA updater.

    :param process_noise_rate: variance added per second of elapsed time in the predict
        step. Larger ⇒ the filter trusts new data faster (tracks change); smaller ⇒
        smoother, slower to react. Calibrate against how fast the real variable drifts.
    :param default_observation_variance: used when an observation carries no ``std``.
    """

    def __init__(
        self,
        store: StateStore[KalmanCellState],
        *,
        process_noise_rate: float = 1e-4,
        default_observation_variance: float = 1.0,
    ) -> None:
        if process_noise_rate < 0.0:
            raise ValueError("process_noise_rate must be non-negative")
        if default_observation_variance <= 0.0:
            raise ValueError("default_observation_variance must be positive")
        self._store = store
        self._process_noise_rate = process_noise_rate
        self._default_obs_variance = default_observation_variance

    def apply_observation(self, observation: GlobalObservation) -> KalmanCellState:
        """Fold one observation into its cell and return the new versioned state."""
        current = self._store.get_state(observation.cell_id)
        if current is None:
            current = KalmanCellState(cell_id=observation.cell_id)

        new_state = current.model_copy(deep=True)
        variable = VARIABLE_FIELDS.get(observation.variable, observation.variable)
        obs_variance = self._observation_variance(observation)
        prior = current.estimates.get(variable)

        if prior is None:
            # First reading of this variable: adopt it directly as the initial belief.
            estimate = Gaussian(observation.value, obs_variance)
        else:
            elapsed = (observation.observed_at - current.last_updated).total_seconds()
            elapsed = max(0.0, elapsed)  # never grow uncertainty on out-of-order events
            predicted = predict(
                Gaussian(prior.mean, prior.variance),
                process_variance=self._process_noise_rate * elapsed,
            )
            estimate = correct(
                predicted, measurement=observation.value, measurement_variance=obs_variance
            )

        new_state.estimates[variable] = VariableEstimate(
            mean=estimate.mean, variance=estimate.variance
        )
        new_state.version = current.version + 1
        new_state.last_updated = observation.observed_at
        if observation.source and observation.source not in new_state.sources:
            new_state.sources.append(observation.source)

        self._store.save_state(new_state)
        return new_state

    def _observation_variance(self, observation: GlobalObservation) -> float:
        """Measurement variance from the observation's σ (carrier of source confidence)."""
        if observation.std is not None and observation.std > 0.0:
            return observation.std**2
        return self._default_obs_variance
