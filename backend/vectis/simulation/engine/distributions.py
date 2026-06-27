"""Statistical distribution wrappers for the Monte Carlo sampler.

Thin, **vectorized** adapters over ``scipy.stats``. Each wrapper draws a whole
vector of ``size`` samples in one C-level call (no Python loop) and threads an
explicit ``numpy.random.Generator`` as ``random_state`` so draws are
reproducible: same generator state ⇒ same samples.

Why ``scipy.stats`` + a numpy ``Generator``: scipy gives the named distribution
families the modelling layer reasons in (Normal, Lognormal, Uniform, Poisson),
while the numpy ``Generator`` is the single, seedable entropy source we can
``spawn`` into independent streams for chunked/parallel execution. Pure math —
no LLM ever touches this path (the V2 Golden Rule).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np
from scipy import stats

from vectis.simulation.schemas import DistributionFamily, StateVariable


class Distribution(ABC):
    """A sampleable 1-D distribution. Stateless; randomness is injected per call."""

    @abstractmethod
    def sample(self, rng: np.random.Generator, size: int) -> np.ndarray:
        """Draw ``size`` samples as a float64 array using ``rng`` for entropy."""
        raise NotImplementedError


@dataclass(frozen=True)
class Normal(Distribution):
    """Gaussian ``N(mu, sigma²)``."""

    mu: float
    sigma: float

    def sample(self, rng: np.random.Generator, size: int) -> np.ndarray:
        return np.asarray(
            stats.norm.rvs(loc=self.mu, scale=self.sigma, size=size, random_state=rng),
            dtype=float,
        )


@dataclass(frozen=True)
class Lognormal(Distribution):
    """Lognormal with median ``median`` and log-space sigma ``sigma``.

    Parameterized so ``median`` is in real units (e.g. km/h) — convenient for a
    strictly-positive quantity like wind speed — and ``sigma`` is the standard
    deviation of the underlying normal in log-space.
    """

    median: float
    sigma: float

    def sample(self, rng: np.random.Generator, size: int) -> np.ndarray:
        return np.asarray(
            stats.lognorm.rvs(s=self.sigma, scale=self.median, size=size, random_state=rng),
            dtype=float,
        )


@dataclass(frozen=True)
class Uniform(Distribution):
    """Uniform on ``[low, high]``."""

    low: float
    high: float

    def sample(self, rng: np.random.Generator, size: int) -> np.ndarray:
        return np.asarray(
            stats.uniform.rvs(
                loc=self.low, scale=self.high - self.low, size=size, random_state=rng
            ),
            dtype=float,
        )


@dataclass(frozen=True)
class Poisson(Distribution):
    """Poisson counts with rate ``lam`` (e.g. ignition events per day)."""

    lam: float

    def sample(self, rng: np.random.Generator, size: int) -> np.ndarray:
        return np.asarray(
            stats.poisson.rvs(mu=self.lam, size=size, random_state=rng), dtype=float
        )


@dataclass(frozen=True)
class Constant(Distribution):
    """Degenerate distribution — a known value with no uncertainty."""

    value: float

    def sample(self, rng: np.random.Generator, size: int) -> np.ndarray:
        return np.full(size, self.value, dtype=float)


def distribution_for(var: StateVariable) -> Distribution:
    """Map a :class:`StateVariable`'s uncertainty parameters to a :class:`Distribution`.

    Raises ``ValueError`` if the variable's family is missing the parameters it
    needs (e.g. a NORMAL with no ``std``) — failing loud beats sampling garbage.
    """
    family = var.family
    if family is DistributionFamily.NORMAL:
        if var.std is None:
            raise ValueError(f"{var.name!r}: NORMAL requires 'std'.")
        return Normal(var.value, var.std)
    if family is DistributionFamily.LOGNORMAL:
        if var.std is None:
            raise ValueError(f"{var.name!r}: LOGNORMAL requires 'std' (log-space sigma).")
        return Lognormal(var.value, var.std)
    if family is DistributionFamily.UNIFORM:
        if var.low is None or var.high is None:
            raise ValueError(f"{var.name!r}: UNIFORM requires 'low' and 'high'.")
        return Uniform(var.low, var.high)
    if family is DistributionFamily.POISSON:
        return Poisson(var.value)
    if family is DistributionFamily.DETERMINISTIC:
        return Constant(var.value)
    raise ValueError(f"{var.name!r}: unhandled distribution family {family!r}.")
