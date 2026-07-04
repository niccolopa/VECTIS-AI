# Scale limits — the honest ceilings

> **What this document is.** VECTIS runs a global grid, but "global" is not "infinite".
> This is the honest statement of where a **single node** stops keeping up, which numbers
> are measured vs. projected, and what the tightest bottleneck actually is. No inflated
> claims. Every measured number here comes from a script you can run yourself.

**Reproduce:** `make global-stress` (the V4 shared-compute-loop stress test),
`make storm` (the tiering back-pressure proof), `make stress` (the Monte Carlo engine).

**Measured on:** Windows AMD64, **12 logical cores**, Python 3.11.3, single process,
production budgets (`VECTIS_MAX_T1_PER_CYCLE=64`, `VECTIS_MAX_T2_PER_CYCLE=5`). Absolute
latencies scale with your CPU; the *shape* of the ceilings does not. These are
single-run numbers on a developer laptop, not a benchmarked mean.

> **Orthogonal caveat — accuracy is not throughput.** Everything below measures how much
> the pipeline can *process*, not how *right* the numbers are. Every hazard model still
> runs the honestly-uncalibrated illustrative coefficients (see
> [`calibration_report.md`](calibration_report.md)): no hazard in this repo has ever been
> fitted to real labels. Scaling the compute does not make an uncalibrated forecast
> correct.

---

## The tiers, and where each one tops out

VECTIS is bounded by design: a cheap screen over the whole active set, then two
hard-budgeted expensive tiers. Each tier has a different ceiling.

| Tier | What runs | Hard budget | Measured cost | Ceiling |
|---|---|---|---|---|
| **T0 — screening** | Vectorized risk index over the active hot set, once per tick | none (it's cheap) | 40k-cell full sweep **< 1 s**; 100k cells **361 ms** single-threaded (Session 32) | ~**100k active cells/tick** on one core before the sweep dominates the tick |
| **T1 — deep forecast** | Full vectorized Monte Carlo + Gaussian Bayesian update, per promoted cell | **64/cycle** | 64 forecasts in **~0.5–0.6 s** | **64 deep forecasts per tick** — a hard cap, never exceeded |
| **T2 — board narration** | The decision board / LLM narration pass | **5/cycle** | 5 mock narrations in ~0.5 s; a **real** LLM call is seconds each | **5 narrations per tick** — and with a real LLM this is a *latency/cost* ceiling, not a CPU one |

The budgets are the ceilings *on purpose*. Promotion is bounded so planetary scale stays
computationally bounded: raising a budget raises the per-tick cost linearly, it does not
unlock free work.

---

## Memory: bounded by the hot set, not the planet

Memory tracks the **active** cell set, never the size of Earth. The `EvictingStateStore`
(TTL + hard LRU cap, default `maxsize=100_000`) guarantees it.

- Measured: **~32–38 MB** peak Python heap for a **40,000-cell** active planet (≈ **1 KB/cell**).
- Projected: a full **100k-cell** hot set (the default LRU cap) ≈ **~100 MB** — trivially
  single-node.
- The bound is a *hard delete*: an untouched cell is evicted and re-born on next touch
  (proved in `tests/realtime/test_global_grid_scale.py`, streaming 100k observations
  against a 2k cap). Attention (viewport / watchlist) exempts watched cells from *idle*
  eviction but **never** from the LRU cap — memory safety always wins.

So the memory ceiling is a policy choice, not a wall: `maxsize` cells resident, whatever
you set it to, independent of how many observations stream through.

---

## The tightest bottleneck: the T2 board budget

**Confirmed still true (Session 33 → Session 40).** Under a storm — thousands of cells
crossing the promotion threshold at once — the two expensive tiers absorb the surge as
**deeper queues, never a melted cycle**, and drain at their budgets once the storm passes.
The drain rates are asymmetric:

At the peak stress level (**40,000 cells crossing simultaneously**):

- **T1** backlog drains in **~625 cycles** (40,000 ÷ 64/cycle).
- **T2** backlog drains in **~8,000 cycles** (40,000 ÷ 5/cycle) — **~13× longer**.

The T2 board/LLM stage is the stage that **cannot be widened cheaply**: T0 is vectorized
NumPy and T1 is a hard CPU budget, but each T2 narration is an LLM call whose latency and
per-call cost you pay directly. With a real provider, 5/cycle is already generous —
the ceiling becomes *LLM throughput and budget*, not CPU.

**This is a feature, not a failure.** The promotion gates and the Session-22 change gate
mean only cells that are genuinely high-risk *and* materially moved ever reach T2, so the
real narration demand is a small fraction of the raw hot set. Back-pressure is surfaced,
not hidden: `TieringMetrics.waited_over_one_cycle` reports queue aging every cycle so an
operator (or an autoscaler) sees the board falling behind before it matters.

### What "graceful degradation" costs, concretely

At a 30 s tick, a 40,000-cell T2 backlog draining at 5/cycle is **~66 hours** to narrate
*every* cell — but that is the entire planet on fire at once, and the change gate means
most of those cells never actually queue for a narration. Cycle **latency stays flat**
(≤ ~1.5 s at every intensity we measured); the surge shows up as queue depth, which is
exactly where you want it. Nothing is dropped — losers wait and are reconsidered next
cycle with fresh evidence.

---

## The single-node envelope (and when to leave it)

One VECTIS process, on a 12-core laptop, comfortably runs:

- a **~100k active-cell** global hot set, screened **every tick**,
- **64** full Monte Carlo + Bayesian deep forecasts per tick,
- **5** board narrations per tick,
- in **tens of MB**, with **sub-1.5 s** cycles even when the whole hot set goes critical.

That is enough for a genuinely worldwide operational picture on a single box. You would
outgrow it when you need **either** more than ~100k cells resident at once (raise the LRU
cap until memory or sweep time bites), **or** sustained deep-analysis / narration demand
above the per-tick budgets for a long time (not a spike — the queues handle spikes).

At that point, scale **horizontally**, not by inflating budgets: the state store, event
broker, and simulation dispatch all sit behind seams with Redis / distributed adapters
already in place (`RedisStateStore`, `RedisStreamBroker`, `simulation/engine/distributed.py`).
Horizontal scale is **available, not required** — see
[`deployment.md`](deployment.md) for the single-node stack that ships as the default.
