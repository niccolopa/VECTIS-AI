"""The 1D Kalman filter math — predict, correct, and the gain that balances them.

A single scalar variable's belief is a Gaussian :class:`Gaussian` ``(mean, variance)``.
Two pure steps move it through time:

- **predict** — with no new data, the estimate stays put but grows *less* certain:
  ``variance += process_variance``. For a slow-moving climate variable the dynamics are
  static (the mean does not drift on its own); only uncertainty accumulates with elapsed
  time, which is what makes a stale estimate trust the next observation more.
- **correct** — fold in an observation ``(measurement, measurement_variance)``. The
  **Kalman gain** ``K = predicted_var / (predicted_var + measurement_var)`` is the
  fraction of the residual we believe: a near-certain observation (small variance) pulls
  K→1 and the estimate snaps to it; a noisy one (large variance) pulls K→0 and the
  estimate barely moves. The corrected variance ``(1 − K)·predicted_var`` is always
  ≤ both inputs — every consistent observation *reduces* uncertainty.

Worked example (the brief's): predict 30 °C with variance 4; observe 32 °C with
variance 1 → K = 4/5 = 0.8 → mean = 30 + 0.8·2 = **31.6 °C**, variance = 0.2·4 =
**0.8** (lower than either side). See :func:`demo`.

Pure functions over plain floats — trivially vectorizable and unit-testable, no LLM.
"""

from __future__ import annotations

from typing import NamedTuple


class Gaussian(NamedTuple):
    """A scalar belief: a ``mean`` estimate and the ``variance`` (uncertainty) around it."""

    mean: float
    variance: float


def predict(prior: Gaussian, *, process_variance: float) -> Gaussian:
    """Project a belief forward when no observation is available.

    Static-dynamics model: the mean is unchanged, the variance grows by
    ``process_variance`` (typically ``process_noise_rate × seconds_elapsed``). The
    longer since the last update, the more uncertain — so the next correction leans
    harder on the observation.
    """
    if process_variance < 0.0:
        raise ValueError("process_variance must be non-negative")
    return Gaussian(prior.mean, prior.variance + process_variance)


def kalman_gain(predicted_variance: float, measurement_variance: float) -> float:
    """Fraction of the prediction→observation residual to trust (0 = ignore, 1 = adopt)."""
    denom = predicted_variance + measurement_variance
    if denom <= 0.0:
        return 0.0  # both sides perfectly certain — nothing to learn; keep the prediction
    return predicted_variance / denom


def correct(predicted: Gaussian, *, measurement: float, measurement_variance: float) -> Gaussian:
    """Fuse an observation into a predicted belief, returning the corrected Gaussian.

    Output variance is always ≤ ``predicted.variance`` (and ≤ ``measurement_variance``):
    combining two independent estimates is never *less* certain than either alone.
    """
    if measurement_variance < 0.0:
        raise ValueError("measurement_variance must be non-negative")
    gain = kalman_gain(predicted.variance, measurement_variance)
    mean = predicted.mean + gain * (measurement - predicted.mean)
    variance = (1.0 - gain) * predicted.variance
    return Gaussian(mean, variance)


def confidence_to_variance(confidence: float, *, base_variance: float = 1.0) -> float:
    """Map a source confidence in ``[0, 1]`` to an observation variance.

    The bridge from a :class:`~vectis.realtime.events.base.GlobalEvent`'s ``confidence``
    to the Kalman ``measurement_variance``: full confidence (1.0) → ``base_variance``;
    lower confidence inflates the variance (``base_variance / confidence``) so an
    untrusted reading moves the estimate less. Confidence 0 → infinite variance (the
    observation is ignored, gain → 0).
    """
    if not 0.0 <= confidence <= 1.0:
        raise ValueError("confidence must be in [0, 1]")
    if confidence == 0.0:
        return float("inf")
    return base_variance / confidence


def demo() -> None:
    """Self-check: the brief's worked example + the convergence guarantee."""
    # Worked example: high-variance prediction + low-variance observation → trust the obs.
    result = correct(Gaussian(30.0, 4.0), measurement=32.0, measurement_variance=1.0)
    assert abs(result.mean - 31.6) < 1e-9, result.mean
    assert abs(result.variance - 0.8) < 1e-9, result.variance

    # Convergence: repeated consistent observations drive variance monotonically down.
    belief = Gaussian(20.0, 10.0)
    last_var = belief.variance
    for _ in range(20):
        belief = predict(belief, process_variance=0.01)
        belief = correct(belief, measurement=25.0, measurement_variance=1.0)
        assert belief.variance < last_var
        last_var = belief.variance
    assert abs(belief.mean - 25.0) < 0.1, belief.mean  # converged onto the true value
    print(f"OK  example={result}  converged={belief}")


if __name__ == "__main__":
    demo()
