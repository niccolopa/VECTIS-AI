# VECTIS V3 — Continuous Global State Management (Blueprint)

> **Status:** design blueprint (Session 16). Defines how V3 represents and
> continuously estimates the state of the *whole world*. No filters or persistence
> are implemented yet — this is the contract.

See the pipeline context in
[`v3_realtime_architecture.md`](v3_realtime_architecture.md). This document zooms
into one stage: **State** and its **Update**.

---

## From one twin to a global field

V2's State was a single `RegionTwin` for California, held in memory and updated on
demand. V3's State is a **continuous field over a global grid**: for every active
cell on Earth, a current estimate of its physical variables *and the uncertainty
around them*, kept live by a streaming filter.

The shift in one line: V2 asked *"what is California's state right now?"*; V3 maintains
*"what is the state of every place we have data for, and how sure are we?"* — always,
without being asked.

### The global grid

The world is discretized into cells (e.g. an H3 hex grid or a lat/lon raster — the
exact tiling is a `state/` implementation detail behind a `CellId`). A cell is the
unit of:

- **Identity** — `CellId` (the grid index) replaces V2's single `region: str`.
- **Independence** — each cell's Update is independent, so cells shard cleanly.
- **Sparsity** — only cells with recent Observations are materialized; the globe is
  mostly empty at any instant, so State size tracks *activity*, not area.

---

## What a cell's State holds

For each active cell, the State is a **belief**, not a point — a mean vector and a
covariance, so uncertainty is first-class (this is what makes a Kalman/Bayesian
update well-posed):

```
CellState
├── cell: CellId                     # which patch of the world
├── mean:  vector of variables       # e.g. temp_anomaly, rainfall, fuel, ignition
├── covariance: matrix               # uncertainty + cross-variable correlation
├── scenario_belief: ScenarioSet     # discrete posterior (reuses V2 ScenarioSet)
├── updated_at: timestamp            # last Observation folded in
└── provenance: source attribution   # which streams shaped this estimate
```

`GlobalState` is then the (sparse) collection of `CellState`s plus the bookkeeping to
look one up, list active cells, and age stale ones out.

Two complementary representations coexist on purpose:

- **Continuous variables** (temperature, rainfall, fuel moisture) → tracked by a
  **Kalman filter** (Gaussian mean + covariance), which is the right tool for noisy
  continuous sensor streams.
- **Discrete scenario belief** (which future is unfolding) → tracked by the existing
  **V2 Bayesian updater** over a `ScenarioSet`. V3 reuses it unchanged.

---

## The Update: continuous, incremental, O(1)

Every processed Observation triggers an **Update** — never a recompute. This is the
heart of "continuous":

```
                    ┌──────────── predict ───────────┐
   CellState(t-1) ──┤ evolve state forward in time    ├──▶ prior(t)
                    │ (motion/decay model + grow cov) │
                    └─────────────────────────────────┘
                                   │
        Observation(t) ───────────▶│ correct
                                   ▼
                    ┌──────────── update ────────────┐
                    │ Kalman gain blends prior with   │──▶ CellState(t)
                    │ observation by their variances  │    (lower covariance)
                    └─────────────────────────────────┘
```

**Predict–correct (Kalman):**
1. **Predict** — evolve the last estimate forward to the Observation's time using a
   simple dynamics model (e.g. anomalies decay toward climatology; covariance grows
   with elapsed time → the longer since we last saw data, the less certain we are).
2. **Correct** — blend the predicted prior with the new Observation, weighted by their
   relative uncertainties (the Kalman gain). A precise Observation pulls the estimate
   hard; a noisy one barely moves it. The result has *lower* covariance — we learned
   something.

Both steps are constant-time per cell and need only the previous `CellState` and the
new Observation — no history replay. State stays bounded; throughput stays flat as
the event stream grows.

The discrete scenario belief is updated in the same step by handing the Observation
to the V2 `BayesianUpdater`, keeping the continuous field and the scenario posterior
consistent.

---

## The `StateEstimator` contract

`realtime/state/` defines the `StateEstimator` ABC — the continuous-stream
generalization of V2's on-demand updater. It owns the predict–correct loop and the
`GlobalState`, and is written to be fed by a stream (one Observation or a batched
window at a time), so the implementation can be in-process today and a partitioned
worker pool later without changing callers.

Key properties the ABC encodes:

- **Continuous, not request/response** — `update(observation)` mutates the live State
  and returns the new `CellState`; there is no "run the whole thing" entry point.
- **Batch-friendly** — a window of Observations for a cell can be folded in one call,
  so processors can coalesce bursts (the scale lever from the architecture doc).
- **Uncertainty-aware** — every estimate carries covariance, so a `Forecast` can be
  drawn from the *distribution* of the state, not a point.
- **Engine-agnostic math** — the filter math is pure `numpy`/`scipy`; like all of
  `simulation/`, it never imports the agents/LLM layer (the Math Firewall holds).

---

## Persistence & lifecycle

State must survive restarts and not grow without bound:

- **Hot tier (memory):** active cells with recent Observations, for O(1) Updates.
- **Warm/cold tier (persisted):** cells that have gone quiet are checkpointed to a
  store (reuse the S2 `database/` layer; Redis/columnar later) and reloaded on demand.
- **Ageing policy:** a cell with no Observation for longer than a TTL is evicted from
  the hot tier (its covariance has grown so wide it carries little information anyway).
- **Belief trajectory:** periodic `CellState` snapshots make the *history* of a cell's
  estimate queryable and auditable — the foundation for V3 calibration and replay.

This is the V2 `StateManager` lesson (one in-memory registry behind a small
interface) scaled out: the same `get / put / active-cells / evict` surface, now
backed by a hot/cold store and keyed by `CellId` instead of a single region string.

---

## Why this is bottleneck-resistant (summary)

- Per-cell independence → horizontal sharding, no global lock.
- Incremental O(1) Updates → throughput independent of event history.
- Sparse, aged State → memory tracks activity, not planetary area.
- Batched windows → bounded Update rate under bursty streams.
- Async/transport-agnostic interfaces → in-process stub and Kafka workers are swaps.

Next session (S17) implements the first concrete `StateEstimator` (a Kalman filter
for the continuous climate variables) against this contract.
