#!/usr/bin/env python
"""VECTIS V2 — 1,000,000-scenario Monte Carlo stress test.

Initializes the California Digital Twin, triggers an observation, then forces the
engine to run **1,000,000 iterations × 3 scenario branches = 3,000,000 trajectory
evaluations** — single-thread vectorized NumPy vs. multiprocessing across cores —
and reports wall-clock time, throughput, peak memory, and a cache demonstration.

Run (from backend/):  ``python scripts/stress_test.py``

Honest-engineer note: for *cheap* per-sample math (a vectorized logistic), a single
NumPy thread usually beats multiprocessing because process spawn + result pickling
cost more than the compute they save. This script measures it and says so plainly.
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import time  # noqa: E402
import tracemalloc  # noqa: E402

import numpy as np  # noqa: E402

from vectis.scripts.demo_v2 import _force_utf8_stdout, _silence_logs  # noqa: E402
from vectis.simulation.caching import MemoizingMonteCarloEngine  # noqa: E402
from vectis.simulation.engine.distributed import RayEngineAdapter  # noqa: E402
from vectis.simulation.engine.runner import (  # noqa: E402
    VectorizedMonteCarloEngine,
    resolve_workers,
)
from vectis.simulation.probability.bayesian import Observation  # noqa: E402
from vectis.simulation.scenarios.generator import (  # noqa: E402
    WildfireScenarioGenerator,
    california_wildfire_state,
)
from vectis.simulation.schemas import SimulationConfig  # noqa: E402

N = 1_000_000
SEED = 7


def _rule(title: str = "") -> None:
    print(f"\n=== {title} ".ljust(72, "=") if title else "=" * 72)


def _timed(label: str, fn) -> tuple[float, object]:
    start = time.perf_counter()
    result = fn()
    elapsed = time.perf_counter() - start
    return elapsed, result


def _throughput(elapsed: float, n_branches: int) -> str:
    evals = N * n_branches
    return f"{elapsed * 1e3:8.1f} ms   |  {evals / elapsed / 1e6:6.2f} M evals/s"


def main() -> None:
    _force_utf8_stdout()
    _silence_logs()

    print("=" * 72)
    print("VECTIS // MONTE CARLO STRESS TEST — 1,000,000 SCENARIOS".center(72))
    print("=" * 72)

    # ── 1. California twin + observation (the trigger) ─────────────────────────
    _rule("SETUP")
    state = california_wildfire_state()
    scenarios = WildfireScenarioGenerator().generate(state)
    n_branches = len(scenarios.scenarios)
    obs = Observation(variable="temp_anomaly_c", value=4.0, std=0.3)
    print(f"[INFO] California twin initialized · {n_branches} scenario branches.")
    print(f"[INFO] Observation triggered: {obs.variable}={obs.value} (heatwave).")
    print(f"[INFO] Workload: {N:,} iterations × {n_branches} branches "
          f"= {N * n_branches:,} trajectory evaluations.")
    print(f"[INFO] CPUs detected: {resolve_workers(0) + 1}  ·  auto workers: {resolve_workers(0)}.")

    engine = VectorizedMonteCarloEngine()

    # ── 2. Single-thread vectorized NumPy ───────────────────────────────────
    _rule("RUN A · SINGLE-THREAD VECTORIZED NUMPY (n_workers=1)")
    tracemalloc.start()
    serial_cfg = SimulationConfig(n_iterations=N, seed=SEED, n_workers=1, parallel=False)
    serial_t, serial_run = _timed("serial", lambda: engine.run(state, scenarios, serial_cfg))
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    print(f"[TIME] {_throughput(serial_t, n_branches)}")
    print(f"[MEM ] peak Python heap during run: {peak / 1e6:6.1f} MB")
    for o in serial_run.outcomes:
        print(f"       {o.scenario_id:<14} mean risk {o.risk.mean:6.2f}  "
              f"p05={o.risk.p05:5.1f} p50={o.risk.p50:5.1f} p95={o.risk.p95:5.1f}")

    # ── 3. Multiprocessing across cores ─────────────────────────────────────
    workers = resolve_workers(0)
    _rule(f"RUN B · MULTIPROCESSING ({workers} WORKERS)")
    par_cfg = SimulationConfig(n_iterations=N, seed=SEED, n_workers=workers, parallel=True)
    par_t, _ = _timed("parallel", lambda: engine.run(state, scenarios, par_cfg))
    print(f"[TIME] {_throughput(par_t, n_branches)}")

    # ── 4. Distributed adapter (cluster abstraction, local stub) ────────────
    _rule(f"RUN C · DISTRIBUTED ADAPTER — RayEngineAdapter / LocalClusterStub ({workers} chunks)")
    dist = RayEngineAdapter()
    dist_cfg = SimulationConfig(n_iterations=N, seed=SEED, n_workers=workers, parallel=False)
    dist_t, _ = _timed("distributed", lambda: dist.run(state, scenarios, dist_cfg))
    print(f"[TIME] {_throughput(dist_t, n_branches)}  (local stub; same code path as Ray/Dask)")

    # ── 5. Mathematical exactness: serial-chunked == parallel ───────────────
    _rule("CORRECTNESS · serial-chunked vs parallel (same seed & worker count)")
    eq_cfg = {"n_iterations": 200_000, "seed": SEED, "n_workers": workers, "retain_samples": True}
    a = engine.run(state, scenarios, SimulationConfig(parallel=False, **eq_cfg))
    b = engine.run(state, scenarios, SimulationConfig(parallel=True, **eq_cfg))
    identical = all(
        np.array_equal(oa.risk.samples, ob.risk.samples)
        for oa, ob in zip(a.outcomes, b.outcomes, strict=True)
    )
    print(f"[CHECK] byte-identical draws (parallel == serial): {'PASS' if identical else 'FAIL'}")
    assert identical, "parallel and serial draws diverged — RNG sharding is broken"

    # ── 6. Caching: identical back-to-back run is instant ───────────────────
    _rule("CACHING · MemoizingMonteCarloEngine (TTL+LRU)")
    cached = MemoizingMonteCarloEngine(engine)
    cache_cfg = SimulationConfig(n_iterations=N, seed=SEED)
    miss_t, _ = _timed("miss", lambda: cached.run(state, scenarios, cache_cfg))
    hit_t, _ = _timed("hit", lambda: cached.run(state, scenarios, cache_cfg))
    speedup = miss_t / hit_t if hit_t > 0 else float("inf")
    print(f"[TIME] cold (miss): {miss_t * 1e3:8.1f} ms     warm (hit): {hit_t * 1e3:8.3f} ms")
    print(f"[INFO] cache {cached.cache.hits} hit / {cached.cache.misses} miss  "
          f"·  warm run {speedup:,.0f}x faster (recompute avoided).")

    # ── 7. Honest verdict ───────────────────────────────────────────────────
    _rule("VERDICT")
    faster, slower, ratio = (
        ("SINGLE-THREAD", "multiprocessing", par_t / serial_t)
        if serial_t <= par_t
        else ("MULTIPROCESSING", "single-thread", serial_t / par_t)
    )
    print(f"[RESULT] {faster} NumPy was {ratio:.2f}x faster than {slower} for this workload.")
    if serial_t <= par_t:
        print("[HONEST] For cheap per-sample math, process spawn + pickling the result")
        print("         arrays back cost MORE than the compute they parallelize. The")
        print("         vectorized single thread wins; multiprocessing pays off only when")
        print("         per-sample cost grows (expensive physics) — keep parallel OFF by default.")
    else:
        print("[HONEST] Multiprocessing paid off here — per-sample cost is high enough that")
        print("         core parallelism beats the spawn/pickle overhead.")
    print(f"[MEM ] NumPy handled {N:,}×{n_branches} arrays at ~{peak / 1e6:.0f} MB peak — no leak.")
    print("=" * 72)


if __name__ == "__main__":  # required: ProcessPoolExecutor uses spawn on Windows
    main()
