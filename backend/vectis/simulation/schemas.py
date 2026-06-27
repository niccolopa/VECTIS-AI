"""V2 Simulation Engine — domain contracts (the probabilistic spine).

These Pydantic models are the shared vocabulary of the V2 layer, exactly as
``core/schemas.py`` is for V1. They encode the four core concepts of the
simulation engine — **State**, **Scenario**, **Simulation Run**, and
**Probability Distribution** — as strictly-typed, serializable objects.

Design rules (mirroring V1):
- These are **data containers**, not calculators. They carry numbers; the engine
  interfaces (``engine/``, ``probability/``) compute them. No Monte Carlo or
  statistical logic lives here — that would violate the V2 Golden Rule of keeping
  computation in deterministic/probabilistic libraries behind explicit interfaces.
- Probabilities are in ``[0, 1]``; risk scores reuse V1's 0–100 scale and
  :class:`~vectis.core.schemas.RiskBand` so V1 and V2 speak the same risk units.
- Raw sample arrays stay as ``list[float]`` (JSON-serializable); ``numpy`` lives
  inside the engine, never on the wire.

This module imports only from ``core`` (shared vocabulary), Pydantic, and the
stdlib — never from ``vectis.agents``. The simulation layer is a pure service.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field, computed_field, model_validator

from vectis.core.schemas import RiskBand


def _utcnow() -> datetime:
    return datetime.now(UTC)


# ─────────────────────────────────────────────────────────────────────────────
# State — the digital twin of the world *now*
# ─────────────────────────────────────────────────────────────────────────────
class DistributionFamily(StrEnum):
    """How a state variable's uncertainty is parameterized.

    Tells the Monte Carlo sampler which law to draw the variable's starting
    value from. Extend as the engine grows (e.g. ``LOGNORMAL``, ``BETA``).
    """

    NORMAL = "normal"
    UNIFORM = "uniform"
    LOGNORMAL = "lognormal"
    POISSON = "poisson"  # counts (e.g. ignition events); ``value`` is the rate λ
    DETERMINISTIC = "deterministic"  # a known constant (no uncertainty)


class StateVariable(BaseModel):
    """One estimated quantity of the world, *with its uncertainty*.

    A V1 feature is a point (e.g. ``temp_anomaly_c = 2.0``). A V2 state variable
    is a *distribution* over that point — the estimate plus how confident we are
    in it — because forecasting honest futures requires propagating uncertainty,
    not just a best guess.

    ``std`` is the standard deviation for ``NORMAL``/``LOGNORMAL``; for
    ``UNIFORM`` use ``low``/``high``; for ``DETERMINISTIC`` only ``value`` is read.
    """

    name: str
    value: float = Field(description="Point estimate (mean / nominal value).")
    family: DistributionFamily = DistributionFamily.DETERMINISTIC
    std: float | None = Field(default=None, ge=0.0)
    low: float | None = None
    high: float | None = None
    unit: str = ""


class WorldState(BaseModel):
    """A digital-twin snapshot: the estimated state of a region at a point in time.

    This is the *initial condition* every simulation starts from. It is produced
    by State Estimation (``states/``) from external data and the V1 feature
    pipeline, and consumed by Scenario Generation and the Monte Carlo engine.
    """

    region: str
    estimated_at: datetime = Field(default_factory=_utcnow)
    variables: list[StateVariable] = Field(default_factory=list)

    def variable(self, name: str) -> StateVariable | None:
        """Look up a state variable by name (convenience, no computation)."""
        return next((v for v in self.variables if v.name == name), None)


# ─────────────────────────────────────────────────────────────────────────────
# Scenario — a weighted hypothesis about the future
# ─────────────────────────────────────────────────────────────────────────────
class Scenario(BaseModel):
    """A named, parameterized hypothesis about how the future unfolds.

    A scenario perturbs the :class:`WorldState` (additive shifts to named
    variables, applied before sampling) and carries a **prior probability** — our
    belief, *before* simulating, that this is the branch reality takes.
    Bayesian updating (``probability/``) revises ``prior`` as observations arrive.
    """

    id: str
    name: str
    description: str = ""
    perturbations: dict[str, float] = Field(
        default_factory=dict,
        description="Additive shift applied to each named state variable's value.",
    )
    prior: float = Field(ge=0.0, le=1.0, description="Prior probability of this branch.")


class ScenarioSet(BaseModel):
    """A mutually-exclusive, collectively-exhaustive set of scenarios.

    The priors form a probability distribution over futures, so they **must sum
    to 1** (within tolerance). This invariant is what makes the engine's output a
    real probability rather than a pile of unweighted what-ifs.
    """

    scenarios: list[Scenario] = Field(default_factory=list)

    @model_validator(mode="after")
    def _priors_sum_to_one(self) -> ScenarioSet:
        if self.scenarios:
            total = sum(s.prior for s in self.scenarios)
            if abs(total - 1.0) > 1e-6:
                raise ValueError(
                    f"Scenario priors must sum to 1.0, got {total:.6f}. "
                    "A ScenarioSet is a probability distribution over futures."
                )
        return self


# ─────────────────────────────────────────────────────────────────────────────
# Probability Distribution — the reduced output of a simulation
# ─────────────────────────────────────────────────────────────────────────────
class ProbabilityDistribution(BaseModel):
    """Summary of the Monte Carlo outcome samples for one variable.

    Produced by reducing raw draws (see ``probability/``) into the statistics
    decision-makers actually use: a central estimate, a credible interval, and
    threshold-exceedance probabilities. The raw ``samples`` are optional so the
    object stays light on the wire while remaining auditable when needed.

    All fields are *populated by the engine* — this model performs no statistics.
    """

    variable: str
    mean: float
    std: float = Field(ge=0.0)
    p05: float = Field(description="5th percentile (lower bound of 90% CI).")
    p50: float = Field(description="Median.")
    p95: float = Field(description="95th percentile (upper bound of 90% CI).")
    exceedance: dict[str, float] = Field(
        default_factory=dict,
        description="P(outcome ≥ threshold) per named threshold, each in [0, 1].",
    )
    samples: list[float] | None = Field(
        default=None, description="Raw draws, if retained for audit/plotting."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Simulation Run — config in, results out
# ─────────────────────────────────────────────────────────────────────────────
class SimulationConfig(BaseModel):
    """Parameters controlling one execution of the Monte Carlo engine."""

    n_iterations: int = Field(default=10_000, ge=1, description="Number of MC draws.")
    horizon_days: int = Field(default=30, ge=1, description="Forecast horizon.")
    seed: int | None = Field(
        default=None, description="RNG seed — set for reproducible runs."
    )
    retain_samples: bool = Field(
        default=False, description="Keep raw draws on the output (heavier payload)."
    )
    n_workers: int = Field(
        default=1,
        ge=0,
        description=(
            "Number of independent RNG streams the draws are split across. With "
            "1 (default) the engine runs a single vectorized kernel — fastest for "
            "cheap per-sample math. >1 enables chunked execution. **0 = auto** "
            "(os.cpu_count()-1). Reproducibility is defined per ``(seed, n_workers)`` "
            "pair (changing either changes the draws); note that ``0=auto`` resolves "
            "to a machine-dependent worker count, so it is reproducible only on the "
            "same machine — set an explicit ``n_workers`` for cross-machine determinism."
        ),
    )
    parallel: bool = Field(
        default=False,
        description=(
            "When True and n_workers>1, run chunks on a ProcessPoolExecutor across "
            "CPU cores. Output is identical to the serial-chunked path for the same "
            "``(seed, n_workers)`` — parallelism changes *where* chunks run, not the numbers."
        ),
    )


class ScenarioOutcome(BaseModel):
    """The simulated result for a single scenario within a run."""

    scenario_id: str
    risk: ProbabilityDistribution = Field(
        description="Distribution of the aggregate 0–100 risk score over the horizon."
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def expected_band(self) -> RiskBand:
        """RiskBand of the mean risk — a convenience label over the distribution."""
        return RiskBand.from_score(self.risk.mean)


class SimulationRun(BaseModel):
    """One full execution: config + initial state ref → per-scenario outcomes.

    The top-level deliverable of the engine, consumed downstream by
    ``forecasting/`` (to build a public ``Forecast``) and ultimately by the V1
    Analyst agents (which narrate, never recompute, these numbers).
    """

    run_id: str
    region: str
    config: SimulationConfig
    created_at: datetime = Field(default_factory=_utcnow)
    outcomes: list[ScenarioOutcome] = Field(default_factory=list)


if __name__ == "__main__":
    # ponytail: minimal self-check on the one real invariant — the prior-sum guard.
    ScenarioSet(scenarios=[
        Scenario(id="a", name="A", prior=0.7),
        Scenario(id="b", name="B", prior=0.3),
    ])
    try:
        ScenarioSet(scenarios=[Scenario(id="a", name="A", prior=0.5)])
    except ValueError:
        pass
    else:
        raise AssertionError("priors not summing to 1 must be rejected")
    print("simulation.schemas self-check OK")
