"""Distributed Monte Carlo — the cluster-scheduler abstraction (Ray/Dask).

Local parallelism (``runner.py``) shards a run across CPU cores with a
``ProcessPoolExecutor``. To scale *past one machine* the same shards are instead
submitted to a cluster scheduler (Ray, Dask, a job queue…). This module defines
that seam **without taking a heavy dependency**:

- :class:`DistributedMonteCarloEngine` — a thin base over the vectorized engine
  that overrides only *dispatch*: it maps the (already-sharded, already-seeded)
  chunks through a cluster client instead of a local pool. Sharding, RNG isolation
  (``SeedSequence.spawn``) and reduction are inherited unchanged, so a distributed
  run is **byte-identical** to a local one for the same ``(seed, n_workers)``.
- :class:`RayEngineAdapter` + :class:`LocalClusterStub` — a *runnable stub* that
  mirrors Ray's ``submit``/``gather`` (future) API but executes locally, so the
  architecture is demonstrable and testable today. Swapping in real Ray is a
  drop-in (see :class:`LocalClusterStub` docstring); ``ray`` is never imported.

The chunk payloads are already picklable (pydantic models + a numpy
``SeedSequence`` + an int + a frozen hazard), which is exactly what a real
scheduler needs to ship them to remote workers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any, Protocol

import numpy as np

from vectis.simulation.engine.runner import (
    VectorizedMonteCarloEngine,
    _ChunkArgs,
    _simulate_chunk,
)


class ClusterClient(Protocol):
    """The minimal scheduler surface VECTIS needs — Ray/Dask both satisfy it."""

    def submit(self, fn: Callable[[_ChunkArgs], np.ndarray], arg: _ChunkArgs) -> Any:
        """Schedule ``fn(arg)`` on the cluster; return a future/handle immediately."""
        ...

    def gather(self, handles: list[Any]) -> list[np.ndarray]:
        """Block until all handles resolve; return results in submission order."""
        ...


class DistributedMonteCarloEngine(VectorizedMonteCarloEngine, ABC):
    """Run the vectorized engine's chunks on a cluster instead of a local pool.

    Subclasses implement :meth:`_cluster_map` against their scheduler. Everything
    else — sharding, per-worker seeding, hazard evaluation, reduction — is the
    exact code the local engine uses, so the science cannot diverge.
    """

    name = "distributed_monte_carlo"

    @abstractmethod
    def _cluster_map(self, chunks: list[_ChunkArgs]) -> list[np.ndarray]:
        """Evaluate every chunk on the cluster, preserving order."""
        raise NotImplementedError

    def _dispatch(
        self, chunks: list[_ChunkArgs], *, parallel: bool, n_workers: int
    ) -> list[np.ndarray]:
        # The cluster *is* the parallelism; the local ``parallel`` flag is moot.
        return self._cluster_map(chunks)


class _Future:
    """A trivial eager future — stands in for a Ray ``ObjectRef`` / Dask future."""

    __slots__ = ("value",)

    def __init__(self, value: np.ndarray) -> None:
        self.value = value


class LocalClusterStub:
    """A drop-in stand-in for a Ray/Dask client that runs locally.

    Mirrors the ``submit``/``gather`` (futures) API so the distributed engine's
    code path is identical to a real deployment — only this client changes. To go
    live with Ray::

        import ray
        ray.init(address="auto")
        remote_fn = ray.remote(_simulate_chunk)
        # submit  → remote_fn.remote(arg)        (returns an ObjectRef, non-blocking)
        # gather  → ray.get(list_of_object_refs)  (blocks, preserves order)

    Dask is analogous (``client.submit`` / ``client.gather``). Because the chunk
    payloads are picklable, no other change is needed to ship them to a cluster.
    """

    name = "local-stub"

    def submit(self, fn: Callable[[_ChunkArgs], np.ndarray], arg: _ChunkArgs) -> _Future:
        # A real scheduler returns immediately with a handle; we compute eagerly
        # but keep the future shape so the call sites match a true cluster client.
        return _Future(fn(arg))

    def gather(self, handles: list[_Future]) -> list[np.ndarray]:
        return [h.value for h in handles]


class RayEngineAdapter(DistributedMonteCarloEngine):
    """Distributed engine that submits chunks via a Ray-style :class:`ClusterClient`.

    Defaults to :class:`LocalClusterStub` (runs locally, identical math) so it is
    usable and tested now; pass a real Ray/Dask client to scale across a cluster.
    """

    name = "ray_adapter"

    def __init__(self, hazard: Any | None = None, cluster: ClusterClient | None = None) -> None:
        super().__init__(hazard)
        self.cluster: ClusterClient = cluster or LocalClusterStub()

    def _cluster_map(self, chunks: list[_ChunkArgs]) -> list[np.ndarray]:
        handles = [self.cluster.submit(_simulate_chunk, chunk) for chunk in chunks]
        return self.cluster.gather(handles)
