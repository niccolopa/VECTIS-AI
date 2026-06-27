"""Concrete Monte Carlo engine — vectorized core, optional parallel chunking.

Implements :class:`~vectis.simulation.engine.monte_carlo.MonteCarloEngine`. For
each scenario it draws ``N`` input vectors from the :class:`WorldState`, pushes
them through a vectorized :class:`HazardModel`, and reduces the resulting
per-sample probabilities to a :class:`ProbabilityDistribution`.

Execution model (one code path, two execution modes):
- Draws are always split into ``n_workers`` independent RNG streams via
  ``SeedSequence.spawn`` (``n_workers=1`` ⇒ a single full-size vectorized draw).
- With ``parallel=True`` and ``n_workers>1`` the chunks run on a
  ``ProcessPoolExecutor``; otherwise they run serially in-process. **Both modes
  produce identical numbers** for the same ``(seed, n_workers)`` — parallelism
  changes *where* the math runs, not the result.

The Golden Rule holds structurally: nothing here imports an LLM or the agents
layer; every number comes from numpy/scipy.
"""

from __future__ import annotations

import os
import uuid
from concurrent.futures import ProcessPoolExecutor

import numpy as np

from vectis.simulation.engine.monte_carlo import MonteCarloEngine
from vectis.simulation.engine.sampler import sample_state, split_iterations
from vectis.simulation.models.wildfire import HazardModel, WildfireHazardModel
from vectis.simulation.schemas import (
    ProbabilityDistribution,
    Scenario,
    ScenarioOutcome,
    ScenarioSet,
    SimulationConfig,
    SimulationRun,
    WorldState,
)

# Risk-band exceedance thresholds on the 0–100 scale (see core RiskBand.from_score).
_THRESHOLDS: dict[str, float] = {"high": 50.0, "severe": 75.0}

# A chunk of work shipped to a (possibly remote) worker. All fields are picklable:
# pydantic models, a numpy SeedSequence, an int, and a frozen-dataclass hazard model.
_ChunkArgs = tuple[WorldState, Scenario, np.random.SeedSequence, int, HazardModel]


def resolve_workers(n_workers: int) -> int:
    """Resolve the worker count: ``0`` ⇒ auto (``os.cpu_count()-1``, ≥1); else as given."""
    if n_workers >= 1:
        return n_workers
    return max((os.cpu_count() or 2) - 1, 1)


def _simulate_chunk(args: _ChunkArgs) -> np.ndarray:
    """Sample one chunk and evaluate the hazard — the unit of parallel work.

    Module-level (so it is picklable for ``ProcessPoolExecutor``) and pure: it
    reconstructs its own ``Generator`` from the spawned ``SeedSequence``, so the
    chunk's draws depend only on that seed — not on import order or worker count
    beyond the agreed split.
    """
    state, scenario, seedseq, size, hazard = args
    if size == 0:
        return np.empty(0, dtype=float)
    rng = np.random.default_rng(seedseq)
    inputs = sample_state(state, scenario, rng, size)
    return hazard.fire_probability(inputs)


def _reduce(samples: np.ndarray, retain: bool) -> ProbabilityDistribution:
    """Reduce per-sample risk scores (0–100) to a :class:`ProbabilityDistribution`."""
    p05, p50, p95 = (float(x) for x in np.percentile(samples, [5, 50, 95]))
    exceedance = {name: float(np.mean(samples >= t)) for name, t in _THRESHOLDS.items()}
    return ProbabilityDistribution(
        variable="risk_score",
        mean=float(samples.mean()),
        std=float(samples.std()),
        p05=p05,
        p50=p50,
        p95=p95,
        exceedance=exceedance,
        samples=samples.tolist() if retain else None,
    )


class VectorizedMonteCarloEngine(MonteCarloEngine):
    """Vectorized Monte Carlo engine with optional process-level parallelism."""

    name = "vectorized_monte_carlo"

    def __init__(self, hazard: HazardModel | None = None) -> None:
        self.hazard = hazard or WildfireHazardModel()

    def run(
        self,
        state: WorldState,
        scenarios: ScenarioSet,
        config: SimulationConfig,
    ) -> SimulationRun:
        # Build every scenario's chunks up front and dispatch them through ONE
        # executor (or one cluster gather). This is the efficient sharding for big
        # runs: a single process pool serves all scenarios — not one pool each,
        # which would pay the spawn/import cost per scenario. Results are sliced
        # back per scenario in submission order, so the math is unchanged.
        n_workers = resolve_workers(config.n_workers)
        all_chunks: list[_ChunkArgs] = []
        spans: list[tuple[Scenario, int, int]] = []
        for scenario in scenarios.scenarios:
            chunks = self._build_chunks(state, scenario, config, n_workers)
            spans.append((scenario, len(all_chunks), len(all_chunks) + len(chunks)))
            all_chunks.extend(chunks)

        results = self._dispatch(all_chunks, parallel=config.parallel, n_workers=n_workers)

        outcomes = []
        for scenario, lo, hi in spans:
            risk = np.concatenate(results[lo:hi]) * 100.0  # (N,) on the 0–100 scale
            outcomes.append(
                ScenarioOutcome(scenario_id=scenario.id, risk=_reduce(risk, config.retain_samples))
            )
        return SimulationRun(
            run_id=uuid.uuid4().hex,
            region=state.region,
            config=config,
            outcomes=outcomes,
        )

    def _build_chunks(
        self, state: WorldState, scenario: Scenario, config: SimulationConfig, n_workers: int
    ) -> list[_ChunkArgs]:
        """Shard the request into ``n_workers`` independent, picklable work units.

        Entropy is isolated per worker via ``SeedSequence(seed).spawn(n_workers)``
        — the canonical numpy pattern — so each chunk's draws depend only on its
        spawned seed. This is what makes serial and parallel execution at the same
        ``(seed, n_workers)`` byte-identical: the sharding (here) is fixed; only the
        *dispatch* (below) differs.
        """
        children = np.random.SeedSequence(config.seed).spawn(n_workers)
        sizes = split_iterations(config.n_iterations, n_workers)
        return [
            (state, scenario, child, size, self.hazard)
            for child, size in zip(children, sizes, strict=True)
        ]

    def _dispatch(
        self, chunks: list[_ChunkArgs], *, parallel: bool, n_workers: int
    ) -> list[np.ndarray]:
        """Execute the chunks. Local strategy: process pool, or serial in-process.

        Overridden by :class:`~vectis.simulation.engine.distributed.
        DistributedMonteCarloEngine` to submit chunks to a cluster scheduler — the
        sharding/RNG/reduction above are reused unchanged, so only *where* the math
        runs differs, never the result.
        """
        if parallel and n_workers > 1:
            with ProcessPoolExecutor(max_workers=n_workers) as pool:
                return list(pool.map(_simulate_chunk, chunks))
        # n_workers == 1 ⇒ a single full-size vectorized draw (the fast path).
        return [_simulate_chunk(chunk) for chunk in chunks]
