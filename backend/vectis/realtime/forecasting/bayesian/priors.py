"""Categorical priors over scenarios — held continuously, relaxed toward a baseline.

In an on-demand updater (V2 Session 8) the prior is supplied fresh each call. A
*continuous* updater instead **carries** its belief between ticks: each posterior becomes
the next tick's prior. That introduces a failure mode the batch updater never had — a long
run of one-sided evidence can drive a scenario's probability to a hard 1.0 (others to 0.0),
after which no future observation can ever move it (``0 × likelihood = 0`` forever).

:class:`ScenarioPriors` defends against that with **relaxation**: on every tick the belief
is nudged a small fraction back toward a fixed ``baseline`` distribution::

    p ← (1 − α)·p + α·baseline

Because ``baseline`` is strictly positive, no probability can be pinned at exactly 0 or 1,
so a drastically different observation can always pull the belief back. ``α`` scales with
elapsed time, so a quiet stretch with no observations relaxes the belief toward baseline —
"if nothing new is happening, drift back to the prior expectation."

Pure arithmetic, no LLM — the Math Firewall holds.
"""

from __future__ import annotations

import math

_EPSILON = 1e-12  # floor so a probability is never *exactly* zero (the 0/100 trap guard)


def normalize(weights: dict[str, float]) -> dict[str, float]:
    """Scale non-negative weights to a probability distribution summing to 1."""
    total = math.fsum(weights.values())
    if total <= 0.0:
        raise ValueError("prior weights must sum to a positive value")
    return {k: v / total for k, v in weights.items()}


class ScenarioPriors:
    """Mutable categorical belief over scenarios that relaxes toward a baseline.

    :param priors: initial scenario_id → probability (need not be normalized).
    :param baseline: distribution to relax toward when idle; defaults to the initial
        priors, so absent new evidence the belief returns to where it started.
    :param relax_rate: per-second relaxation strength. ``0`` disables relaxation (the
        belief only moves on evidence). The per-tick fraction is ``1 − exp(−rate·dt)``,
        bounded in ``[0, 1)``, so it never overshoots the baseline.
    """

    def __init__(
        self,
        priors: dict[str, float],
        *,
        baseline: dict[str, float] | None = None,
        relax_rate: float = 0.0,
    ) -> None:
        if relax_rate < 0.0:
            raise ValueError("relax_rate must be non-negative")
        self._probs = normalize(priors)
        self._baseline = normalize(baseline) if baseline is not None else dict(self._probs)
        if set(self._baseline) != set(self._probs):
            raise ValueError("baseline must cover exactly the same scenarios as the priors")
        self._relax_rate = relax_rate

    @property
    def probabilities(self) -> dict[str, float]:
        """The current belief (a copy — callers cannot mutate internal state)."""
        return dict(self._probs)

    @property
    def scenarios(self) -> list[str]:
        return list(self._probs)

    def relax(self, *, elapsed_seconds: float = 1.0) -> dict[str, float]:
        """Nudge the belief toward the baseline by the time-scaled fraction; return it."""
        if self._relax_rate <= 0.0 or elapsed_seconds <= 0.0:
            return self.probabilities
        alpha = 1.0 - math.exp(-self._relax_rate * elapsed_seconds)
        self._probs = {
            sid: (1.0 - alpha) * p + alpha * self._baseline[sid]
            for sid, p in self._probs.items()
        }
        return self.probabilities

    def set(self, posterior: dict[str, float]) -> None:
        """Adopt ``posterior`` as the new belief (normalized, floored off exact zero)."""
        floored = {sid: max(p, _EPSILON) for sid, p in posterior.items()}
        self._probs = normalize(floored)
