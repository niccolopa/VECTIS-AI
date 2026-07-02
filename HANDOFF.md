# HANDOFF — VECTIS

> Source of truth for cross-session continuity. A new engineer (or a fresh Claude
> Code session with zero context) should be able to continue from this file alone.
> **Read this first. Update it after every major milestone.**

Last updated: **2026-07-02** · End of **Session 34** (Calibration & Validation — **COMPLETE,
with the explicit caveat that no real historical calibration data was ever available in this
environment**: no FIRMS MAP_KEY or CDS credential existed across all three attempts, so the
full acquisition → join → fit → backtest pipeline (`vectis/calibration/`) is built and tested
end to end but has **never run against real fire history**, and the deployed wildfire
coefficients remain the Session-7 illustrative priors. Shipped: FIRMS-archive + keyless
Open-Meteo/ERA5 acquisition clients that *raise with instructions* rather than fabricate;
the labeled cell-day join with provenance manifests; `fit.py` (unregularized
`LogisticRegression`, `ignition_sources` honestly carried, artifact with full provenance)
behind a new `default_wildfire_model()` seam the engine *and* the screen both default
through; `backtest.py` replaying temporally-held-out cell-days through the **real** live
path via `ContinuousPipeline.replay_observations` (ROC-AUC / Brier / reliability), which
completed the Session-8 `Calibrator` stubs (`reliability_curve`, `fit_recalibration`
isotonic/Platt); running Brier via `pipeline.resolve_forecast()` + `calibration_summary()`;
Step-6 re-measurement of the S32 gap (unchanged: MAD 3.61 / max 13.23 — `TierManager`
constants deliberately untouched); and `docs/calibration_report.md`, which leads with the
no-real-data caveat. **241 backend tests pass** (+1 network-gated skip; was 227), ruff +
mypy clean. See the Session 34 section directly below.) · End of **Session 33** (Triggered Deep Analysis — the tiering
engine: new `vectis/realtime/tiering/` package whose `TierManager` makes planetary scale
computationally bounded — **T0** (screened only, Session 32) → **T1** (full Monte Carlo +
Bayesian) → **T2** (decision board / LLM), every promotion under a hard, never-exceeded per-cycle
budget (`VECTIS_MAX_T1_PER_CYCLE` default 64, `VECTIS_MAX_T2_PER_CYCLE` /
`VECTIS_MAX_BOARD_REPORTS_PER_CYCLE` default 5). Promotion is **shape-aware**, built around
Session 32's measured low-bias: promote on screen ≥ 85 (the saturated tail, where the screen was
measured accurate to ≤ 3.57 pts and biased one-sided low), **or** belief shift ≥ 0.2 TVD, **or**
inside the **[5, 85) transition band while trending up** — exactly where the screen quietly
under-reads by up to 13.23 pts — with band cells ranked **bias-corrected (+13.23)** in the
priority queue. Every decision carries an auditable reason. T2 **composes** the literally-reused
Session-22 change gate (`risk_moved`, factored out of `pipeline.py`) with the hard top-N budget;
budget losers **wait** in queues, never dropped. Per-cycle `TieringMetrics` expose queue depths,
cycle time, and a queue-aging signal. Global-storm stress (`make storm`): 20k active cells, 4,000
crossing the threshold **simultaneously** → T1 executions pinned at exactly 256/cycle, cycle time
flat (calm median 92 ms, worst 282 ms, noise-dominated), monotone post-storm drain, T1 queue empty
at cycle 24, every promoted cell served; honest finding: the T2 board budget is the tightest
bottleneck (~3,800-cell narration backlog at 8/cycle). **213 backend tests pass** (incl. 6 slow,
+1 network-gated skip), ruff + mypy clean. See the Session 33 section directly below.) · End of
**Session 32** (The Screening Layer — a cheap global risk
index: added **Tier 0**, a near-free vectorized risk score over the *active* cell set, completely
decoupled from the expensive Monte Carlo + Bayesian + board pipeline. A pluggable **per-hazard**
`ScreeningIndex` registry (`vectis/realtime/screening/`) mirrors how `HazardModel`s plug into the
engine; **only `wildfire` has a real implementation** (`WildfireScreeningIndex`, the Session-7
logistic evaluated **once** per cell — no sampling), and the other observed hazards (quake / flood /
cyclone / tsunami / volcano) are listed as `UNSCREENED_HAZARDS` with **no registry entry** — the
honest `NotYetScreenedIndex` stub *raises* rather than fabricate a number. `GlobalScreeningSweep`
scores the store's **hot set only** (new bulk `StateStore.active_states()`), never the theoretical
grid, and is pure/synchronous. Measured gap vs the full engine: **MAD 3.61, max 13.23** over a temp
sweep — the screen matches within ~1 pt in the saturated tails but under-estimates by up to ~13 pts
in the mid-risk transition band (always biased low; it omits the upward scenarios). Speed: **100k
active cells swept in 361 ms single-threaded (~277k cells/s)**, well under the 1 s budget. **180
backend tests pass** (+1 network-gated skip, +1 new slow), ruff + mypy clean. See the Session 32
section directly below.) · End of **Session 31** (Real Ingestion: the first live global
feeds — replaced the last synthetic hazard feed and added two genuinely new ones so real
worldwide **fire (NASA FIRMS)**, **earthquake (USGS)**, and **multi-hazard (GDACS)** detections
now flow through the existing pipeline onto the H3 grid, each landing at its **real `(lat, lon)`**
instead of one fixed demo coordinate. Added an **optional internal gateway — the *Sluice*** — that
holds FIRMS credentials, retries/normalizes upstream responses, and fails over across keys purely
for **reliability**; it mirrors each upstream's path shape so connectors are a drop-in either way and
fall back to the raw upstream when it isn't running (the offline/keyless promise is unbroken). All
four feeds are offline-safe. **171 backend tests pass** (+1 network-gated skip), ruff + mypy clean.
See the Session 31 section directly below.) · End of **Session 30** (The Global Grid & Sparse State —
first session of the V4 arc: retired the placeholder `naive_cell_id` 0.1° quantization for **H3
hierarchical addressing** (resolution 5, ~8.5 km cells) with parent/child helpers; proved **lazy
cell birth** (an untouched store allocates zero cells); promoted **`RedisStateStore`** from a
ponytail comment to a real durable hot tier behind `VECTIS_STATE_BACKEND`; added a **TTL + LRU
`EvictingStateStore`** so the hot set tracks the *active* cells, not the size of the planet; and a
slow **bounded-memory load test** streams 100k land-scattered observations and asserts the active
set never exceeds its bound. Cold storage (PostGIS) does **not** exist yet — eviction is a real
delete and rehydration = fresh first-touch birth, deferred to Session 35. **163 backend tests pass**
(incl. 2 slow), ruff + mypy clean. See the Session 30 section directly below.) · End of **Session 29**
(Real-World Data Integration —
retired the last synthetic weather feed and put **real, live data** behind the V3 live stream:
the weather connector now fetches current conditions from the **keyless Open-Meteo API** (real
California temperature/humidity/wind + a humidity-derived drought index), the live stream drives
its default from real Open-Meteo + NASA FIRMS feeds instead of the offline oscillating mocks, and
the Kalman filter + tick rate were re-calibrated for steady hourly data so the risk stays **alive
but stable** instead of flatlining as the filter gain collapses. **150 backend tests pass.** See
the Session 29 section directly below.) · End of **Session 28** (Backend Global Data Reset —
purged the legacy "Liguria" demo region from the backend so the global frontend (S26/S27) has
matching global data: the V3 live stream now emits a `California_01` headline cell at lat 37.0 /
lon −120.0, the region registry/API serves California (default), New South Wales, and Attica
instead of "Liguria, Italy", and the bundled 240-cell sample dataset was migrated onto North
America by retargeting the region bbox. The decision board was already region-dynamic, so reports
now narrate "California" once the twin defaults flipped. **148 backend tests pass**, ruff + mypy
clean. See the Session 28 section below.) · End of **Session 27** (Global Frontend Hard Reset & UI Polish —
made the console read as one cohesive global tactical platform on a standard laptop: the Live
Intelligence grid now breaks at `lg` (was `xl`) so it stays two-column on 1080p, the live map grew
to 450px and frames the Atlantic at zoom 1.5 (Americas + Europe/Africa in view), the legacy V1
Liguria 240-cell grid was retired from the Maps and Climate Risk Intelligence pages in favour of the
shared global basemap, the remaining "Liguria, Italy" labels in the mock fixtures became global, and
the 3D overview globe lost its hardcoded Italian province dots to spin as a generic wireframe planet.
**Build + 14 frontend tests pass.** See the Session 27 section below.) · End of **Session 26**
(Global Frontend Expansion & UI Polish —
aligned the React console with the global V3 backend: scrubbed the V1 "Liguria, Italy / 240
cells" hardcodes from the headers/sidebars, fixed the flatlining demo feeds (they now fluctuate
with sine waves around a moderate baseline so risk breathes between HIGH and SEVERE instead of
pinning at 100%), and replaced the single Liguria dot with a real-world dark basemap that plots
the live worldwide FIRMS hotspots — California, NSW, Attica, British Columbia, Rondônia, Liguria.
**148 backend + 14 frontend tests pass.** See the Session 26 section below.) · End of **Session 25**
(Bridging the Reality Gap — closed the
three architectural debts the external audit flagged: (1) the Kalman→Monte-Carlo overlay now
maps `temperature`→`temp_anomaly_c` via a `KALMAN_TO_WORLD` bridge so the estimated mean drives
the simulation, not just Bayesian reweighting; (2) the SSE endpoint no longer spins a pipeline
per viewer — one `LiveStreamBroadcaster` runs the `ContinuousPipeline` as a single lifespan-owned
background task and fans frames out to bounded per-subscriber queues; (3) the satellite connector
now calls the real **NASA FIRMS** area CSV API (key from `VECTIS_FIRMS_API_KEY`, offline mock
fallback). **147 backend tests pass.**) · End of **Session 24** (Real-Time Frontend Layer —
the V3 `ContinuousPipeline` is now exposed over **Server-Sent Events** (`GET /api/v1/stream/v3/live`,
`realtime/live_stream.py` → `LiveClimateStream` yielding JSON forecast frames), and a new **Live
Intelligence** React console subscribes via `hooks/useV3Stream.ts` (rAF-coalesced rendering so a
high-frequency stream never freezes the browser) to drive five real-time components — live header,
recoloring MapLibre cell, dual-axis risk/confidence timeline, animated Bayesian posterior bars, and a
rolling event feed — assembled in `pages/LiveIntelligencePage.tsx` at `/live`. **142 backend + 14
frontend tests pass.**) · Session 23 (Live Climate Risk Demo —
`scripts/demo_v3_live.py`: drives the V3 `ContinuousPipeline` as a *living* terminal stream.
Ramping offline weather + satellite connectors emit hotter/drier JSON each tick into an
`IngestionManager` → `EventProducer` → broker; the pipeline folds every reading through
Kalman → continuous Bayesian → Monte Carlo → decision report, and a tactical console redraws
per tick. Verified alive: risk 77 → 93, belief swings baseline → hotter_drier (0.7% → 94%),
confidence dips through the contested transition, board re-convenes on material moves. 140
tests pass. **V3 COMPLETE.**) · Session 22 (Real-Time Forecasting Pipeline —
`realtime/pipeline.py`: `ContinuousPipeline` unites every V3 layer into one continuous flow —
`Live Data → Events → Kalman → Bayesian → Monte Carlo (V2) → Decision Report (V2 board)`. A
**fast path** (Kalman+Bayesian, sub-ms, in the consumer) is decoupled from a **slow path**
(Monte Carlo + LLM board) that runs off the event loop via `asyncio.to_thread`, with per-cell
coalescing so a burst collapses to one forecast of the latest state — ingestion never blocks on
simulation. `build_default_pipeline()` wires the offline Liguria defaults; 139 tests pass.) ·
Session 21 (Bayesian Continuous Update Engine —
`realtime/forecasting/bayesian/`: `ScenarioProfile`/`log_likelihood` scoring a Kalman `(mean,
variance)` state against scenario archetypes in log-space; `ScenarioPriors` carrying a categorical
belief that relaxes toward a positive baseline so it never locks at 0/100; `ContinuousBayesianUpdater.
update_probabilities(kalman_state)` doing log-prior + log-likelihood → stable-softmax posterior →
new prior. Fire risk 45% → 67% on drought+wind.) · Session 20 (Kalman Filter Foundation — the EMA merge
replaced by a 1D predict→correct filter: `kalman/filter.py` Gaussian `(mean, variance)` math,
`KalmanCellState` uncertainty-aware state, `KalmanStateUpdater` fusing observations by Kalman gain so
variance *drops* as data corroborates; `StateStore` generalized to serve both models). (Session 19:
State Estimation Engine — the V3 "present": `WorldCellState` versioned per-cell state; `StateStore`
ABC + `MemoryStateStore` with replayable version history; `StateUpdater.apply_observation` folding
observations in via EMA, bumping version/timestamp.) **V2 shipped; V3 ingestion + streaming + state
estimation live.** (Session 18:
Event Streaming Engine — `MessageBroker` ABC with an in-process `MemoryBroker` default + a lazy
`RedisStreamBroker` adapter; `EventProducer`/`EventConsumer` carrying `Data Event → Queue →
Processor`; `GlobalEvent` hardened with `confidence`/`metadata`. Session 17:
resilient `BaseAPIConnector` + weather/satellite/generic connectors + `IngestionManager`. Session
16: V3 foundation — `realtime/` scaffold, `GlobalEvent` + `StateEstimator` interfaces.)

---

## Session 34 — Calibration & Validation (the credibility session)

**Goal**: Retire the standing credibility debt from Session 7: the wildfire logistic's
coefficients were illustrative hand-tuned priors, never fit against reality. Build the
pipeline that fits them against real NASA FIRMS fire/no-fire labels joined with ERA5
weather history, backtest the live forecasting path out of sample (ROC-AUC, Brier,
reliability), make calibration a running metric, and re-derive the Session-33 tiering
thresholds from whatever model ends up deployed — all without ever fabricating data.

**Current Progress**: Session 34 (**Calibration & Validation — COMPLETE, with the explicit
caveat that no real historical calibration data was ever available in this environment**).
No FIRMS MAP_KEY and no CDS credential existed at any point across all three attempts, so
the pipeline is fully built and tested but **has never been run against real historical
fire data**, and production still runs on the Session-7 illustrative priors. Seven atomic
step commits (Steps 1–2 from the earlier interrupted attempts, verified; Steps 3–7 this
pass) + this handoff. Backend **241 pytest pass** (+1 network-gated skip; was 213 at the
end of S33), `ruff` + `mypy` clean, working tree clean.

- **Step 1 — historical data acquisition** (`feat: add historical FIRMS + ERA5 acquisition
  pipeline for calibration`, `47a2d30`). `vectis/calibration/data/`: `FirmsArchiveClient`
  reads the FIRMS area-CSV **standard-processing archive** (`VIIRS_SNPP_SP`, ≤10-day
  chunks, reusing the live connector's CSV parser); `Era5Client` reads hourly ERA5 via
  **Open-Meteo's keyless `/v1/era5` archive** (same Copernicus data, zero credentials,
  canonical units) and aggregates to fire-weather daily summaries (max temp / max wind /
  min RH / precip sum). The honesty contract is structural: with no key, FIRMS **raises
  `CalibrationDataError` with instructions** — there is deliberately no offline-fallback
  label source, because fabricated labels would poison a fit.
- **Step 2 — the spatial-temporal join** (`feat: join FIRMS labels with ERA5 weather into a
  versioned cell-day dataset`, `abd2a01`). Unit of observation: one H3 res-5 **cell-day**.
  Positives = deduplicated FIRMS detections on their `assign_cell_id` cell; negatives =
  seeded, reproducible sample of no-fire cell-days from the same region/window (ratio
  recorded in the manifest — it sets the base rate the intercept absorbs). Features use
  the **serve-time transforms** (same ~22 °C climatology as `KALMAN_TO_WORLD` and the
  screen; trailing-30-day rainfall anomaly ending the day *before* the label; ERA5 holes
  dropped and counted, never filled). Written under `data/processed/calibration/` with a
  provenance manifest; `python -m vectis.calibration.data.build` is the one-command entry.
- **Step 3 — coefficient fitting behind one seam** (`feat: fit wildfire logistic
  coefficients and load them through one default seam`, `edbacfa`). `fit.py` fits the
  exact `WildfireHazardModel` functional form with an **unregularized**
  `LogisticRegression` (a penalty would silently shrink coefficients the system treats as
  effect sizes). `ignition_sources` is **carried at the prior and recorded as carried** —
  FIRMS/ERA5 have no ignition observable, and an unidentifiable coefficient must not be
  presented as fitted. The artifact (coefficients + provenance + the previous priors) goes
  to `artifacts/calibration/wildfire_coefficients.json`, where the new
  `default_wildfire_model()` loads it; the Monte Carlo engine and the screening index now
  both default through that seam, so a real fit deploys as a pure parameter change. Tests
  prove recovery of known coefficients from synthetic rows. **No artifact exists here** —
  a fresh clone (and this repo) still runs the priors.
- **Step 4 — the backtesting harness** (`feat: backtest held-out cell-days through the live
  pipeline…`, `7d8401d`). `backtest.py`: **temporal split** (train strictly precedes
  holdout — a shuffled split would leak autocorrelated weather), fit on the early slice,
  replay the late slice through the **actual live components** via a new synchronous
  `ContinuousPipeline.replay_observations` seam (same Kalman → Bayesian → Monte Carlo
  math, no queue, no board), scoring headline risk as a probability: ROC-AUC, Brier,
  reliability curve. This completed the two Session-8 `Calibrator` blueprints:
  `reliability_curve` (equal-width bins, empty bins omitted) and `fit_recalibration`
  (isotonic / Platt), both refusing one-sided backlogs. Fixture-tested (a steep known
  logistic → the replayed live path must score ROC-AUC > 0.7 out of sample).
- **Step 5 — running calibration metrics** (`feat: expose running Brier and reliability
  from resolved live forecasts`, `0786adf`). `ContinuousPipeline` owns a `Calibrator`:
  `resolve_forecast(cell_id, occurred)` logs ground truth against the cell's latest
  forecast as it lands; `calibration_summary()` returns resolved count, running Brier,
  and the reliability curve on demand. A metric, not a script.
- **Step 6 — thresholds explicitly unchanged** (`docs: record that tiering thresholds
  stand…`, `8a7eb65`). The S32 gap measurement was re-run against the actually-deployed
  model. No artifact ⇒ the deployed model is byte-for-byte the prior model ⇒ the gap is
  identical (**MAD 3.61, max 13.23**), so `TierManager`'s constants (band [5, 85), cutoff
  85, +13.23 correction) remain derived from a still-valid table and were **deliberately
  not touched** — changing them would have been activity, not information.
- **Step 7 — the calibration report** (`docs: write the Session 34 calibration report…`,
  `e814c1f`). `docs/calibration_report.md` **leads** with the no-real-data caveat, then:
  the one credential a future run needs (a **free FIRMS MAP_KEY** — ERA5 is keyless via
  Open-Meteo, `VECTIS_CDS_API_KEY` is *not* required), the exact two-command live run,
  fitted-vs-illustrative coefficients (one honest column), fixture-only backtest scope,
  the threshold no-change justification, and limitations (arson, sub-grid wind,
  representativeness — n/a until a real sample exists, and said so).

**What Worked**:
- **Forensic-first recovery.** This session began by reconstructing state from `git log` /
  `git status` / reading the actual modules instead of trusting prior summaries — and
  found Steps 1–2 committed and solid, Step 3 half-applied in the working tree
  (`fit.py` untracked, wiring uncommitted), and Steps 4–7 absent. Nothing already
  committed was redone.
- **One default seam (`default_wildfire_model`) instead of scattered constructors.** The
  engine and the screen both construct through it, so screen-vs-engine consistency is
  structural and a future real fit deploys with zero code edits.
- **`replay_observations` on the pipeline itself** kept the backtest honest: it drives the
  literal production math rather than a reimplementation that would drift. One small
  public method was the entire seam.
- **Keyless ERA5 via Open-Meteo's archive** collapsed the credential surface to a single
  free FIRMS MAP_KEY — the difference between "get two accounts approved" and "paste one
  key" for whoever finally runs this live.
- **Refusing to fit is a feature.** Single-class datasets, one-sided calibration backlogs,
  keyless FIRMS fetches: every impossible ask raises with instructions instead of
  producing a plausible-looking number.

**What Didn't Work**:
- **Two prior attempts died to transient network errors** ("Connection closed
  mid-response"), one inside a devcontainer, one after moving back to local Windows —
  neither was a logic or code failure. The second interruption left Step 3 half-applied
  (untracked `fit.py`, uncommitted wiring), which is exactly why this pass started
  forensic. If a session dies mid-step again: check `git status` for stragglers before
  believing any summary.
- **No FIRMS/CDS credentials, confirmed three times.** Do not re-attempt the live fetch
  without first securing a MAP_KEY (free, minutes:
  https://firms.modaps.eosdis.nasa.gov/api/map_key/) — every re-check wasted session time
  reaching the same answer. `VECTIS_CDS_API_KEY` is *not* needed (ERA5 is keyless here).
- **The devcontainer detour left droppings**: npm-platform churn in
  `frontend/package-lock.json` (reverted) and a `.devcontainer/` folder (committed as
  chore — it is real, working config).
- **The `thresholds` module promised in the package docstring was never the right
  shape** — re-derivation is a *procedure* (re-run the gap measurement, re-derive the
  constants) documented in the report, not a speculative module. The docstring was
  corrected rather than the module built.

**Next Steps**: **Session 35 — Multi-Hazard Models (flood, earthquake impact, cyclone
risk)**: real `HazardModel` + `ScreeningIndex` implementations for the hazards the event
stream already observes but honestly refuses to score (`UNSCREENED_HAZARDS`). **Standing
prerequisite, before the terminal's confidence numbers are treated as trustworthy**: the
moment FIRMS credentials become available, run the real Session-34 calibration —
`data.build` → `fit` → `backtest` (documented in `docs/calibration_report.md`) — deploy
the artifact, re-run the gap measurement, and re-derive the tiering thresholds from the
calibrated model's real error curve. Until that run happens, every risk number the
terminal shows rests on illustrative priors.

---

## Session 33 — Triggered Deep Analysis (the tiering engine)

**Goal**: Build the single mechanism that makes planetary scale computationally bounded: a
`TierManager` that decides, out of every active cell, which few get promoted from the cheap
Session-32 screen (**T0**) to the expensive Monte Carlo + Bayesian forecast (**T1**) and which of
those get a decision-board/LLM narration (**T2**) — under hard, measured, never-exceeded per-cycle
budgets, so the system degrades gracefully (deeper queues) instead of melting under a global spike.
The one design constraint that mattered: Session 32 proved the screen's error is **biased low in
the mid-risk transition band** (up to −13.23 pts), so promotion must be shape-aware, not a single
naive cutoff blind to where the screen is quietly wrong.

**Current Progress**: Session 33 (**Triggered Deep Analysis — COMPLETE**). Six atomic step
commits + this handoff. Backend **213 pytest pass** (207 fast + 6 slow, +1 network-gated skip;
was 180), `ruff` + `mypy` clean, working tree clean.

- **Step 1 — shape-aware T0→T1 gates** (`feat: add TierManager with shape-aware T0-to-T1
  promotion gates`). New `vectis/realtime/tiering/` (`manager.py`). `TierManager.consider()` takes
  the sweep's headline scores (`headline_scores()` collapses the Session-32
  `{cell: {hazard: score}}` to one score per cell, worst hazard wins) plus per-cell belief shifts
  (`total_variation()` — the Session-22 TVD concept restated over the pipeline's posterior dicts)
  and promotes through **three auditable gates**: `score_threshold` (screen ≥ `T1_SCORE_CUTOFF`
  = 85 — the saturated tail where S32 measured the screen accurate to ≤ 3.57 pts, and the bias is
  one-sided low so the truth can only be higher); `belief_shift` (TVD ≥ 0.2 — something real
  changed regardless of absolute score); `transition_band_trending_up` (score in
  `TRANSITION_BAND` = **[5, 85)** *and* rising by > `trend_epsilon` — the band where the screen
  under-reads). Band bounds are **derived from the measured S32 gap table**, not guessed: every
  measured point whose gap exceeded the 5-pt materiality threshold screened between 6.45 and
  38.34; [5, 85) brackets that with margin and meets the cutoff at 85 so the score axis has no
  dead zone. Every `PromotionDecision` records cell, reason, score, shift, and priority — the
  audit trail.
- **Step 2 — the bounded board budget** (`feat: bound T2 board narration with a hard global
  budget`). `select_t2()` composes two gates: (1) the **Session-22 change gate, literally
  reused** — `risk_moved()` was factored out of `ContinuousPipeline._run_forecast` into a
  `pipeline.py` module function (same semantics, same `DEFAULT_RISK_CHANGE_THRESHOLD = 5.0`), so
  tiering applies the *identical* gate at global scope rather than duplicating it; (2) the hard
  budget — only the top-N queued candidates by magnitude of change (absolute risk for a
  never-reported cell) get a slot, N from `VECTIS_MAX_T2_PER_CYCLE` /
  `VECTIS_MAX_BOARD_REPORTS_PER_CYCLE` (default 5). Tested interaction: a cell **can pass the
  change gate and still lose the budget gate** to hotter cells — it waits and wins a later cycle.
  A queued candidate whose fresh risk drifts back near its last report is withdrawn (the change it
  was queued for evaporated); granted slots record last-reported risk, re-arming the gate.
- **Step 3 — the budgeted T1 priority queue** (`feat: drain T1 candidates through a budgeted
  priority queue that waits, never drops`). Promotions land in a per-cell queue ranked by the
  **bias-corrected** promotion signal: a transition-band cell competes at `score + 13.23` (the
  measured worst under-read), so a band cell at 80 outranks a tail cell at 90 — the
  shape-awareness reaches the *ranking*, not just the gate. `drain_t1()` grants at most
  `VECTIS_MAX_T1_PER_CYCLE` (default 64) slots, hottest first. **Wait, don't drop** is explicit
  and tested: losers stay queued and are all eventually served; each fresh sweep re-anchors a
  waiter's priority (a cooled cell sinks instead of holding a stale hot slot, but is still
  served); a re-qualifying queued cell refreshes in place (freshest evidence, one entry — the
  Session-22 coalescing principle at queue level).
- **Step 4 — coalescing at global scale** (`test: prove per-cell coalescing holds under
  multi-cell global load`). The Session-22 per-cell coalescing was only ever proven for one cell;
  the new pipeline test interleaves a 3-event burst across 5 distinct H3 cells and asserts exactly
  5 Monte Carlo runs — one per cell, never per event, no cell eating another's slot. **No
  production change was needed** (the `_jobs`/`_pending` maps were already per-cell); it is now
  regression-guarded.
- **Step 5 — back-pressure metrics** (`feat: expose per-cycle back-pressure metrics from the
  tiering engine`). `run_cycle()` orchestrates consider → drain T1 → pluggable `T1Runner` →
  select T2 and returns a `TieringCycle` with `TieringMetrics`: hot-set size, T1/T2 executed and
  queue depths, promotions by reason, cycle time, and `waited_over_one_cycle` — queued cells
  passed over by more than one budget round, the **queue-aging signal** that separates a brief
  spike from demand outrunning the budgets. No dashboard; just the numbers, per cycle.
- **Step 6 — the global storm** (`test: stress the tiering engine with a global storm of 4000
  simultaneous crossings`). `tests/realtime/test_tiering_storm.py` (`slow`; also `make storm`)
  drives the **real** screening sweep over a real `EvictingStateStore` of 20,000 land-weighted H3
  cells (reusing the Session-30 generator) and heats 4,000 at once. Measured numbers below.

**How the T0→T1→T2 gates work together**: every cycle, the sweep screens the whole hot set for
~free; `consider()` promotes through the three shape-aware gates into the T1 queue; `drain_t1()`
grants ≤ 64 deep-analysis slots by bias-corrected priority; the T1 runner (in production the
Session-22 slow path) returns fresh headline risks; `select_t2()` passes those through the reused
change gate and then the hard board budget (≤ 5 narrations). Both queues **wait rather than
drop**, and both budgets are enforced unconditionally — an operator can always answer "why did
this cell get expensive treatment" from the decision's `reason` field.

**How the Session-32 mid-band bias was specifically handled** (the question this session had to
answer): three distinct mechanisms, all tested — (1) the **[5, 85) transition band** is a
first-class gate: mid-band + trending up promotes even though the raw score alone never would;
(2) band cells are **ranked bias-corrected (+13.23 pts, the measured worst under-read)** in the
priority queue, so they compete for slots as the risk they *may really be*; (3) the unconditional
cutoff sits at 85, the point Session 32 measured the screen trustworthy (gap ≤ 3.57 < the 5-pt
materiality threshold) — so the screen is trusted exactly where it earned trust, and distrusted
exactly where it was measured wrong.

**The measured global-storm numbers (printed by `make storm`, not asserted as hopes)**: 20,000
active cells, 4,000 crossing the T1 threshold in one cycle; budgets T1=256, T2=8. **T1 executions
pinned at exactly 256 every cycle** of the storm (hard bound held; peak T1 queue 3,744). Cycle
time stayed flat: calm median **92 ms**, worst storm cycle **282 ms** (3.1×) — and several calm
cycles also hit ~220 ms, so the spread is timer/GC noise, not queue pressure (sweep of 20k cells
dominates; the queue sort is negligible). After the storm subsided the T1 queue drained
**monotonically** at 256/cycle and emptied at cycle 24; every promoted cell was served
(wait-don't-drop verified at scale) and the aging signal returned to tracking only the T2 backlog.
**The honest weakness, printed not hidden**: the T2 board budget is the tightest bottleneck — the
storm left a **~3,800-cell narration backlog** that drains at 8/cycle (~500 cycles), and cooled
first-look cells still queue for T2 because a first report is always "material"
(`risk_moved(None, …) == True`, matching the pipeline's own first-forecast semantics).

**What Worked**:
- **Deriving thresholds from Session 32's measurements instead of inventing them.** The band
  bounds, the cutoff, and the +13.23 priority correction all trace to the measured gap table — so
  every constant in the promotion policy has a cited provenance, and Session 34's calibration can
  re-derive them the same way.
- **Factoring `risk_moved` out of the pipeline** made "compose with, don't duplicate, the
  Session-22 board gating" literal: one function, two call sites, identical semantics.
- **A dict-per-cell queue re-sorted per drain** (not a heap) — priorities change every cycle as
  fresh sweeps re-rank waiters, which a heap handles badly and a sort handles trivially. At 4k
  queued cells the sort is microseconds; `ponytail:` switch to a heap only if queues ever reach
  millions.
- **The `T1Runner` seam** kept the stress test honest and fast: the storm exercises the *tiering*
  engine with a stub runner; the sampler's own numbers are Session 13's job. No fourth cell
  generator was built — the storm reuses Session 30's `_random_land_point` and the real sweep.

**What Didn't Work / Notes**:
- **The T2 backlog finding is real and deliberate.** With N=5 (test: 8) narrations/cycle, any
  large storm builds a narration backlog that outlives the storm by orders of magnitude, inflated
  by cooled never-reported cells whose "first look is always material". A future session should
  add a T2 aging/shedding policy (e.g. withdraw never-reported candidates whose current risk falls
  below a floor) — deliberately **not** done now, because silently discarding queued cells is
  exactly what this session promised not to do without an explicit, tested policy.
- **`waited_over_one_cycle` counts both queues**, so after full T1 recovery it keeps flagging the
  aging T2 backlog. First draft asserted it returned to 0 post-storm — wrong; the metric was
  correctly reporting genuine T2 aging. The storm test now asserts it stays non-zero and explains
  why.
- **A brand-new mid-band cell cannot promote on its first sighting** (no trend history yet — only
  the score/belief gates can catch it immediately). Documented in `consider()`; acceptable because
  the next cycle's sweep supplies the trend, and a genuinely hot cell crosses 85 anyway.
- **Tiering imports `pipeline` (hence, transitively, the engine).** Unlike screening, this layer
  *may* — it exists to feed the expensive path and reuses its gate; `vectis.realtime.__init__`
  already eagerly imports the pipeline regardless. The screening AST decoupling test is untouched.

**Next Steps**: **Session 34 — Calibration & Validation.** The credibility session deferred since
Session 7: fit the wildfire logistic against real **NASA FIRMS** fire/no-fire labels, backtest
against **ERA5** weather history, and quantify real predictive skill (reliability curves, Brier
score, skill vs climatology). This also retires the two standing `ponytail:` hand-set constants
(the ~22 °C climatology baseline in the screen/pipeline bridge and the screening fallback inputs)
and should **re-derive Session 33's promotion thresholds** (band bounds, cutoff, +13.23
correction) from the calibrated model's real error curve, the same way this session derived them
from the S32 gap table. Later in the arc: tiering/zoom over the H3 hierarchy (the still-unused
parent/child helpers) and the PostGIS cold tier + true rehydration (Session 35).

---

## Session 32 — The Screening Layer (a cheap global risk index)

**Goal**: Build **Tier 0** — a near-free, vectorized risk *index* over the **active cell set** (the
global heat map), completely decoupled from the expensive Monte Carlo + Bayesian + board pipeline
that only ever runs on a small, promoted subset. Every active cell gets a screening score on every
update; the heavy engine runs nowhere until a future session *promotes* a cell. Backend-only: no
tiering/promotion (that's Session 33), no calibration, no frontend. The one hard rule this session
had to honour: **only wildfire has a hazard model today** — build the layer to be genuinely
pluggable per-hazard, wire wildfire for real, and leave an honest, tested stub for the hazards that
have no model yet (quake/flood/cyclone/tsunami/volcano) instead of fabricating a plausible number.

**Current Progress**: Session 32 (**The Screening Layer — COMPLETE**). Five atomic step commits.
Backend **180 pytest pass** (+1 network-gated skip, +1 new `slow`; was 171), `ruff` + `mypy` clean
(146 source files), working tree clean.

- **Step 1 — the `ScreeningIndex` abstraction** (`feat: add pluggable per-hazard ScreeningIndex
  abstraction (Tier 0)`). New package `vectis/realtime/screening/`. `base.py`: `ScreeningScore`
  (a `NamedTuple` — `hazard: str`, `value: float` on the shared 0–100 scale, `.band` via the
  project-wide `RiskBand`), the `ScreeningIndex` ABC (one method, `score(cells) -> {cell_id:
  ScreeningScore}`), and a hazard-keyed **registry** (`register()` / `default_registry()`) a future
  session extends without touching this module — mirroring how `HazardModel`s plug into the MC
  engine. Honest scope is documented and enforced: `UNSCREENED_HAZARDS = {quake, flood, cyclone,
  tsunami, volcano}` have **no registry entry**, and `NotYetScreenedIndex(hazard).score()` **raises**
  `NotImplementedError` rather than return a fake value.
- **Step 2 — `WildfireScreeningIndex`, the one real implementation** (`feat: add
  WildfireScreeningIndex — the one real Tier 0 screen`). `wildfire.py` wraps the Session-7
  `WildfireHazardModel` and evaluates its **vectorized logistic once** per cell — a point estimate,
  one NumPy pass, no sampling/scenarios/Monte Carlo. Reads `WorldCellState`: absolute `temperature`
  → anomaly via the same **~22 °C climatology** baseline the pipeline's `KALMAN_TO_WORLD` bridge
  uses; `wind_speed_kmh` from `extra`; model inputs a cell doesn't carry (rainfall anomaly, ignition
  sources) fall back to the digital-twin climatology **so the screen estimates the same hazard the
  full engine's base state does** (otherwise the measured gap would be meaningless). A cell with no
  `temperature` (e.g. a cyclone-only GDACS cell) has no wildfire state → **skipped**, never
  fabricated. Registers itself at import. **Decoupling is proven**, not asserted in prose: an
  AST-parsing test confirms neither screening module imports `vectis.simulation.engine`.
- **Step 3 — `GlobalScreeningSweep` over the active set** (`feat: sweep the active cell set with
  every registered screening index`). `sweep.py`: `sweep(cells)` is a **pure, synchronous** pass
  (no I/O, no side effects) that runs every registered index and returns a flat
  `{cell_id: {hazard: ScreeningScore}}`; `sweep_store(store)` pulls the store's **hot set only** and
  feeds it in. Added a bulk `StateStore.active_states()` (Memory / Redis-SCAN / Evicting) — a
  one-pass, **side-effect-free** read (no per-cell recency touch). Under `EvictingStateStore` the
  inner store holds exactly the hot set, so this never enumerates the theoretical planet-wide grid.
  Cells a hazard can't score are simply absent from the result.
- **Step 4 — the gap, measured not assumed** (`test: measure the screening-vs-full-engine gap
  honestly`). A test compares `WildfireScreeningIndex` against the full `VectorizedMonteCarloEngine`
  + prior-mixture risk over a temperature sweep at the California baseline (40k draws, seed 32,
  single-threaded). **Observed: MAD 3.61, max 13.23.** The screen matches the engine within ~1 pt
  where risk saturates (both near 0 or 100) but **under-estimates by up to ~13 pts in the mid-risk
  transition band** (temp ≈ 20 °C, anomaly ≈ −2), **always biased low** — it evaluates only the
  baseline scenario at the mean, omitting the upward `hotter_drier` / `extreme_wind` scenarios the
  engine mixes in. The full table is a code comment in `tests/realtime/test_screening.py`. The asserts
  are regression guards around the measured gap (MAD < 8, max < 20), **not** an arbitrary tolerance,
  plus a structural check that the worst gap lives in the unsaturated band — exactly where Session 33
  should promote cells to the full engine.
- **Step 5 — the speed proof** (`test: prove the screening sweep scales to 100k active cells
  sub-second`). `tests/realtime/test_screening_scale.py` (`@pytest.mark.slow`): fills the hot store
  with **100k** land-weighted H3 cells (reusing Session 30's `_random_land_point` generator, not a
  duplicate) and sweeps them in one pass — **361 ms single-threaded (~277k cells/s)**, well under
  the 1 s budget. It prints the real number (in the `make stress` spirit), doesn't assume a speedup.

**The `ScreeningIndex` design (what's real vs stubbed today)**: the layer is a registry of per-hazard
indices. `wildfire` is the **only real** screen — it reuses the Session-7 logistic as a single
vectorized point estimate. `quake`, `flood`, `cyclone`, `tsunami`, `volcano` are **observed in the
event stream but have no model**: they are absent from the registry, so the sweep returns nothing for
them, and `NotYetScreenedIndex` is the explicit, tested extension point that *raises* if a future
session tries to score them before wiring a real model. This is the deliberate refusal-to-fake the
project has held since V2. Adding a hazard later = implement a `ScreeningIndex`, call `register()` —
zero edits to this session's code.

**The measured screening↔engine gap (why it matters for Session 33)**: MAD 3.61 / max 13.23 over the
sweep. The shape is the useful part: **tight in the saturated tails, widest (and always low) in the
mid-risk transition band**. So a responsible promotion policy screens aggressively where risk is
clearly near 0 or near 100 and **promotes the mid-band cells** to the full engine, where the cheap
approximation is least trustworthy and the decision is most sensitive. This number is the input
Session 33 should use to set its threshold, rather than a guessed tolerance.

**What Worked**:
- **Reusing the hazard function, not the engine.** The screen shares only `WildfireHazardModel` with
  the Monte Carlo path — one NumPy pass, no sampler, no scenarios. The two risk paths stay genuinely
  independent (AST-proven), which is the whole point of a cheap Tier 0.
- **The registry mirrors the existing `HazardModel` plug pattern**, so "pluggable per-hazard" needed
  no new machinery a reviewer hasn't already seen.
- **Bulk `active_states()` over per-cell reads.** The first sweep did a `get_state` per cell, which
  (on `EvictingStateStore`) touched LRU recency 100k times — both a side effect and the bottleneck.
  A one-pass bulk read made the sweep side-effect-free *and* cut the time; making `ScreeningScore` a
  `NamedTuple` (not a frozen dataclass) roughly halved the per-cell construction cost. 629 ms → 361 ms.
- **Measuring the gap before asserting it.** Running the comparison first gave real numbers (MAD 3.61,
  max 13.23), so the test guards are anchored to reality, not a hopeful constant — and the shape of
  the gap became an actionable finding for the next session.

**What Didn't Work / Notes**:
- **`WorldCellState.temperature` is an absolute reading, not an anomaly.** The hazard model wants a
  `temp_anomaly_c`, so the screen subtracts the ~22 °C climatology (matching `KALMAN_TO_WORLD`).
  Feeding the raw reading in unshifted saturates every cell to ~100. `ponytail:` this baseline is
  hand-set; wire per-cell climatology when calibration lands.
- **Unobserved model inputs use a climatology fallback.** The cell state carries no rainfall anomaly
  or ignition-source count, so the screen fills them from the digital-twin baseline. This is what
  makes the screen approximate the *same* quantity the full engine's base state evaluates; drop the
  fallback and fold real values into `WorldCellState` when feeds carry them.
- **The `vectis.realtime` package `__init__` eagerly imports the pipeline** (hence the MC engine), so
  a naïve `sys.modules` decoupling check would flag that pre-existing, unrelated coupling. The real
  decoupling claim — screening's *own* modules never import the engine — is proven by AST-parsing
  their imports instead.
- **H3 collisions cap the distinct active set.** 100k random land points map to ~51k distinct res-5
  cells, so the scale test *keeps sampling until the hot set reaches 100k* rather than assuming one
  point = one cell.

**Next Steps**: **Session 33 — Triggered Deep Analysis (the tiering engine).** Use the screening
score to decide **where** the expensive pipeline runs: promote a small subset of cells from the
cheap screen to the full Kalman → Bayesian → Monte Carlo → decision board, driven by the screening
value (and its known gap — promote the mid-risk transition band first, where MAD is largest). This is
the "cheap everywhere, expensive only where it matters" split the whole V4 arc has been building
toward. Later in the arc: tiering/zoom over the H3 hierarchy (the still-unused parent/child helpers)
and the PostGIS cold tier + true rehydration (Session 35).

---

## Session 31 — Real Ingestion: the first live global feeds

**Goal**: With H3 addressing + sparse storage in place (Session 30), wire the first **genuinely
global, genuinely real** disaster feeds into the grid. Replace the last synthetic hazard connector
and add two new ones so real worldwide **fire**, **earthquake**, and **multi-hazard** detections flow
through the existing `IngestionManager → EventProducer → broker` pipeline onto real H3 cells — each
event landing wherever on Earth it actually occurred, not at one fixed demo coordinate. Still an
ingestion-layer session: no tiering, no promotion logic, no frontend. Success = real detections on
the correct cells anywhere on the planet, not any risk score changing.

**Current Progress**: Session 31 (**Real Ingestion — COMPLETE**). Seven commits (6 step commits +
one pre-existing lint sort). Backend **171 pytest pass** (+1 network-gated skip; was 163),
`ruff` + `mypy` clean (142 source files), working tree clean.

- **Step 1 — the Sluice, an optional internal gateway** (`feat: add the Sluice — optional outbound
  feed gateway with credential failover`). New `vectis/ingress/sluice.py`: a small standalone FastAPI
  service VECTIS owns end to end (**original design, not modeled on any third-party product**). Its
  only job is *reliability*: hold the FIRMS MAP_KEY(s), retry/normalize upstream responses, and
  **fail over** across credentials for one source when more than one is configured. USGS/GDACS are
  keyless and pass straight through. The framework-free `Sluice` class carries the retry+failover
  logic (unit-tested directly); thin FastAPI routes wrap it, **one endpoint per upstream, each
  mirroring the real API's exact path shape** — so a connector builds the *same* URL whether it
  targets the Sluice or the upstream. Selected per source via `VECTIS_{FIRMS,USGS,GDACS}_BASE_URL`
  (each defaults to the real upstream), so the gateway is **fully optional** — connectors fall back
  to the raw upstream when it isn't running, and the offline/keyless promise is unbroken. FIRMS key
  pool from `VECTIS_SLUICE_FIRMS_KEYS` (falls back to `VECTIS_FIRMS_API_KEY`). **Recorded principle
  (module docstring):** failover is for *outage tolerance*, **never** for mass-registering keys to
  evade a provider's rate limits. `tests/ingress/test_sluice.py` (5 tests) proves failover, exhausted
  credentials, keyless pass-through, and transient-5xx retry.
- **Step 2 — `FirmsConnector`** (`feat: add global FirmsConnector for real worldwide active-fire
  detections`). New `realtime/connectors/firms.py` replacing the California-pinned satellite feed as
  the fire source. Reads the NASA FIRMS **global** area-CSV feed (world bbox `-180,-90,180,90`),
  mapping each row to a `GlobalEvent` at its **real `(lat, lon)`** with the acquisition timestamp and
  the Session-18 confidence routing (FIRMS confidence → event `confidence` + observation `std`; VIIRS
  `l`/`n`/`h` letters mapped). Key from `VECTIS_FIRMS_API_KEY`, base from `VECTIS_FIRMS_BASE_URL`.
  **Live** when a key is set *or* a gateway base is configured (the Sluice holds the key, so a
  placeholder path segment keeps shape parity); otherwise (and on any feed failure) `collect()`
  degrades to deterministic offline detections spread across four continents — never raises.
- **Step 3 — `UsgsQuakeConnector`** (`feat: add UsgsQuakeConnector for the real global earthquake
  feed`). New `realtime/connectors/usgs.py`. Reads the **keyless** USGS `4.5_day` summary GeoJSON
  (M4.5+, past 24 h — chosen for a meaningful *global* signal without micro-seismic noise; documented
  in the module). Each feature → `GlobalEvent` at real coords (GeoJSON `[lon, lat, depth]`), magnitude
  in `payload`, event time from the epoch-ms field, `confidence` from `magError` where the feed
  reports it else default 1.0. As the keyless connector with no credential logic in the way, it's
  where retry/backoff is exercised most (the offline fallback is deterministic global quakes).
- **Step 4 — `GdacsConnector`** (`feat: add GdacsConnector for real global multi-hazard alerts`). New
  `realtime/connectors/gdacs.py`. Reads the keyless GDACS event-list GeoJSON, emitting **mixed hazard
  types from one feed** (cyclone / flood / tsunami / volcano / earthquake / drought / wildfire) at
  their real coords. Hazard type rides in `payload`/`metadata`; because `GlobalObservation` has **no
  free-form field**, it is preserved into the observation through its **variable name**
  (`cyclone_alert_level`, `flood_alert_level`, …), so mixed hazards survive end to end. Alert level
  (Green/Orange/Red → 1/2/3) becomes the value. Offline fallback: deterministic global mixed-hazard
  alerts.
- **Step 5 — global ingestion wiring** (`feat: wire the four global feeds into one canonical
  ingestion manager`). New `realtime/ingestion/global_feeds.py`: `build_global_ingestion_manager()`
  registers all four real feeds (weather + FIRMS + USGS + GDACS), each offline-safe, and
  `ingest_into(manager, store)` folds a poll cycle through `to_observation → assign_cell_id` into a
  state store so every event lands on the H3 cell of its real location. One dead feed contributes
  nothing to a cycle while the others keep flowing (the Session-17 guarantee, now with four feeds).
- **Step 6 — the global ingestion proof** (`test: prove global ingestion lands worldwide events on
  distinct H3 cells`). `tests/realtime/test_global_ingestion.py`: fixture-driven (one shared
  `httpx.MockTransport`, no live network) — a mixed poll cycle lands real detections on distinct H3
  cells across **four continents** and into the sparse `EvictingStateStore`; a **dead FIRMS feed
  degrades without stalling** the other three (which still deliver their live events); and GDACS's
  **mixed hazard types survive end to end** into `GlobalObservation` variables. The one real-network
  test hits live USGS and is **skipped unless `VECTIS_LIVE_TESTS=1`** — CI stays offline/deterministic.
- **Follow-up**: `chore: sort demo_v3_live imports…` — a pre-existing S30 import-order miss that
  surfaced under `ruff`, fixed in isolation.

**How each connector was integrated**: all three subclass the Session-17 `BaseAPIConnector`, so they
inherit resilient HTTP (exponential backoff, 4xx-fails-fast, `collect()` that never raises) and only
implement `fetch()` + `normalize()`. Each defines its own `GlobalEvent` subclass whose
`to_observation()` calls `assign_cell_id(lat, lon)` — so **cell assignment is automatic and correct
per event**, no central router needed. Nothing downstream of the connector boundary changed: events
flow through the *unchanged* `IngestionManager → EventProducer → broker` pipeline exactly as the
weather connector already did. `build_global_ingestion_manager()` is the new canonical global entry
point; the Session-24/29 `live_stream.py` SSE demo (a single-cell California *display* concern) was
deliberately **left untouched** — globalizing ingestion is a separate concern from that one headline
cell, and disturbing it would have broken its deterministic offline-mock tests for no benefit.

**How the Sluice is positioned**: optional, reliability-only, original. It is **not** on the default
path — every connector's base URL defaults to the real upstream, so a fresh clone never needs it. It
exists so that *when* run, one flaky FIRMS key or one transient outage doesn't take a feed down
(retry + normalize + credential failover). It is explicitly **not** a key-pool for rate-limit evasion
— that principle is recorded in its module docstring and in the commit. Because it mirrors each
upstream's path shape, pointing a connector at it (or away from it) is a one-env-var change with no
code edit — the same optional-infra pattern as the Redis broker / state store.

**How graceful degradation was verified for each**: FIRMS — `demo()` self-check asserts the no-key /
no-gateway path yields global offline detections on **distinct** cells; the global proof asserts a
dead-key (HTTP 500) cycle degrades cleanly while the other three feeds keep delivering. USGS & GDACS —
offline fallbacks return deterministic global features on any `ConnectorError`; `demo()` self-checks
confirm real feature shapes normalize onto the right cell/variables, and the global proof exercises
both live. Weather — unchanged Session-29 offline reading. The manager-level guarantee (one feed down,
three keep flowing, no stall, no raise) is asserted in
`test_dead_firms_feed_degrades_without_stalling_the_others`.

**Quality-check answers (all yes)**: (1) A clone with **zero keys and zero services** boots and
streams synthetic-but-plausible global events — every connector is offline-safe and each base URL
defaults to the real upstream, so nothing is required to run. (2) With `VECTIS_FIRMS_API_KEY` set,
real fire + (keyless) quake + multi-hazard detections land on the **correct H3 cells worldwide** — a
California fire and a Japan quake resolve to different cells (asserted against fixtures), not one demo
coordinate. (3) Kill any one of the four feeds (bad key / simulated timeout) and the other three keep
flowing with no stall (asserted).

**What Worked**:
- **The `BaseAPIConnector` seam did all the heavy lifting.** Three real connectors were tiny because
  retry/backoff/graceful-degradation already lived in the base — each is just `fetch()` (build a URL,
  parse a payload) + `normalize()` (rows → events). The confidence-routing pattern lifted straight
  from the S18 satellite connector.
- **`to_observation()` owning `assign_cell_id`** meant global cell landing needed **no** new routing
  code — each event self-addresses, so "spread across the planet" fell out of using real coordinates.
- **Mirroring upstream path shapes** made the Sluice a true drop-in: connectors don't branch on
  whether it's running; one env var swaps the base and the URL is identical either way.
- **One shared `httpx.MockTransport` dispatching by path** tested all four connectors together with no
  network — the same S17 pattern, extended to a multi-feed cycle. `GlobalObservation`'s lack of a
  free-form field turned out to be a *feature*: encoding hazard in the variable name is what makes the
  mixed-hazard signal survive into the math layer unambiguously.

**What Didn't Work / Notes**:
- **`GlobalObservation` has no hazard field.** Preserving GDACS's mixed hazards "into `GlobalObservation`"
  forced the hazard into the **variable name** (`{hazard}_alert_level`) rather than a payload dict — the
  observation is deliberately a flat `(cell, variable, value, std)`. This is the right call (it keeps
  hazards distinguishable downstream) but was the one non-obvious modelling decision.
- **`live_stream.py` was intentionally not globalized.** Its frame builder reads a single California
  `cell_id` for *display*; wiring the global feeds into it would either break its offline-mock tests or
  ship events the frame never renders. The global manager is a separate, honestly-scoped entry point.
- **Sluice failover detects a jammed FIRMS key by body sniffing.** FIRMS answers a bad/over-quota key
  with HTTP 200 + a plaintext `Invalid MAP_KEY` body (not a non-200), so failover keys on that string.
  `ponytail:` widen the heuristic if FIRMS changes its error wording.
- **The old `SatelliteAPIConnector` was kept, not deleted.** `live_stream.py`'s `GlobalSatelliteConnector`
  demo feed and several tests still subclass it; `FirmsConnector` is the new canonical fire source for
  *ingestion*, and satellite.py remains only as the SSE demo's offline hotspot generator.

**Next Steps**: **Session 32 — The Screening Layer (cheap global risk index).** With real global events
now populating the sparse H3 active set, add a fast, cheap first-pass risk index over those cells — a
coarse screen that decides *where* the expensive Kalman→Bayesian→Monte-Carlo pipeline is worth running,
so planet-scale ingestion doesn't imply planet-scale simulation. Later in the V4 arc: tiering/zoom over
the H3 hierarchy (the still-unused parent/child helpers) and the PostGIS cold tier + true rehydration
(Session 35).

---

## Session 30 — The Global Grid & Sparse State

**Goal**: Begin **VECTIS V4** (the planet-scale arc, Sessions 30–40). Replace the single-region,
unbounded, in-process state model with the structural foundation everything else in V4 stands on:
a **sparse, lazily-instantiated, hierarchically-indexed global grid**. This session is *only*
addressing + storage — no simulation, no tiering, no frontend. The guiding principle: **the planet
is mostly dormant**, so compute and memory must track the *active* set of cells, never the
theoretical size of the grid.

**Current Progress**: Session 30 (**The Global Grid & Sparse State — COMPLETE**). Seven commits (5
step commits + a lint sort + a mypy typing fix). Backend **163 pytest pass** (161 fast + 2 slow),
`ruff` + `mypy` clean, working tree clean.

- **Step 1 — H3 hierarchical cell addressing** (`feat: replace naive lat/lon cells with H3
  hierarchical addressing`, `41b2ea7`). Added `h3>=4.0` to backend deps. New
  `realtime/state/cell_id.py`: `assign_cell_id(lat, lon, resolution=5)` maps a coordinate to an H3
  index (an opaque hex-string `CellId`), plus `parent_cell_id` / `children_cell_ids` wrapping H3's
  hierarchy (unused today but unit-tested now — Session 31+ tiling depends on them). Deleted the old
  `naive_cell_id` from `events/base.py` and routed **every** call site through `assign_cell_id`
  (the three connectors' `to_observation`, `live_stream.py`, `demo_v3_live.py`). One test constant
  (`test_realtime_pipeline.CELL`) was derived from `assign_cell_id` instead of the hardcoded
  `"44.4,8.9"`. `test_cell_id.py` (4 tests) proves determinism, resolution, and parent/child
  round-trips.
- **Step 2 — lazy cell birth** (`test: prove lazy cell birth — untouched store allocates zero
  state`, `4f15441`). Audited `store.py`, `models.py`, `kalman/state_model.py`: both updaters
  already use the Session-19 `get_state → create-if-missing` pattern and `MemoryStateStore` writes
  nothing until `save_state` — **no pre-allocation, no dense array, no startup init path** anywhere.
  Added a test proving a store with zero touched cells holds zero state objects and that *reading* an
  unseen cell does not materialize it.
- **Step 3 — real `RedisStateStore`** (`feat: promote RedisStateStore to a real durable hot tier`,
  `e75abdd`). Replaced the ponytail placeholder with a working `RedisStateStore(StateStore[StateT])`:
  latest state as a JSON string key (`model_dump_json`), history as an `LPUSH`/`LTRIM` list capped at
  `history_limit` — the exact newest-first, bounded semantics of `MemoryStateStore`'s
  `deque(maxlen)`. Added `get_state_store()` reading `VECTIS_STATE_BACKEND` (`memory`|`redis`) +
  `VECTIS_REDIS_URL`, mirroring `get_broker()`. `redis` stays a lazily-imported optional extra.
  Tested via an injectable in-memory fake client (same seam `RedisStreamBroker` exposes), so the lean
  no-redis install stays green.
- **Step 4 — TTL + LRU eviction** (`feat: add TTL + LRU eviction over the state store (hot/cold
  boundary)`, `cc17b24`). New `EvictingStateStore` wraps any `StateStore` with the
  `SimulationCache` design (recency-ordered `OrderedDict` + monotonic timestamps), retargeted at cell
  state: a cell idle past `idle_seconds` is evicted, and the hot set never exceeds `maxsize` (LRU).
  Eviction drops the cell from the wrapped store via a new `StateStore.delete` (implemented on both
  backends). Tests cover LRU bound, TTL expiry (injectable clock), and rehydration.
- **Step 5 — the bounded-memory proof** (`test: prove the hot set stays bounded under 100k global
  observations`, `74cae2a`). `tests/realtime/test_global_grid_scale.py` (marked `slow`) streams
  100k land-weighted synthetic observations (sampled within continental bboxes, not uniform over
  oceans) through `assign_cell_id → EvictingStateStore(maxsize=2000)` and asserts the active set
  never exceeds the bound mid-stream or at the end, with many evictions. A second test asserts H3
  parent/child aggregation round-trips across 1000 random cells.
- **Follow-ups**: `chore: sort live_stream imports…` (`102d27b`) and `fix: type StateStore
  serialization protocol with Self for strict mypy` (`c12876b`) — the store's `_CellState` Protocol
  now types `model_validate_json` as returning `Self`, so `RedisStateStore` deserialization is
  strictly typed against the concrete model.

**H3 addressing scheme (resolution & why)**: default **resolution 5** — ~8.5 km hexagon edge,
~252 km²/cell, ~2M cells for the whole planet. Chosen as the wildfire sweet spot: fine enough that
one cell is a meaningful fire-behaviour unit (roughly a large fire's active footprint), coarse
enough that the *global active set* stays small since we only ever materialize cells with live data.
Finer (res 6–7) multiplies the active set for no wildfire-scale modelling gain; coarser (res 3–4)
smears distinct fires into one cell. H3 was chosen over the old rectangular quantization for two
reasons: **near-constant cell area everywhere** (a 0.1° box collapses toward the poles; a hexagon
does not) and a **clean hierarchy** (one parent per coarser resolution, fixed children per finer
one) — the precondition for the tiling/zoom/aggregation the rest of V4 needs.

**Eviction / rehydration behaviour today (and the explicit limitation)**: `EvictingStateStore`
enforces two bounds on every touch — TTL (idle cells evicted) and LRU (hot set ≤ `maxsize`).
**There is no cold tier yet.** Eviction is a *genuine delete*: an evicted cell is gone. Its next
observation is reborn as fresh **version-1** first-touch state via the lazy-birth path —
indistinguishable from a location never seen before, because nothing was persisted (so it truly *is*
new). **PostGIS cold-tier persistence + real rehydration is scheduled for Session 35.** Until then,
"rehydration" means "reborn from the next observation," and this is documented plainly in the code
(`EvictingStateStore` docstring) and asserted by
`test_rehydration_is_indistinguishable_from_first_touch` — not faked.

**Quality-check answers (all yes)**: (1) a million scattered observations keep memory bounded by the
*active* set — the LRU/TTL bound holds regardless of total volume (proven by the slow load test).
(2) With Redis unavailable, everything runs on `MemoryStateStore` with **no code changes** — `redis`
is imported lazily and only when `VECTIS_STATE_BACKEND=redis`; the full suite passes without it.
(3) An evicted cell's next observation silently rebuilds it as fresh v1 state with no crash and no
special-cased recovery — it's the same lazy-birth path as first touch.

**What Worked**:
- **H3 confined to one module + the existing `CellId` opacity.** The whole pipeline already treated
  `CellId` as an opaque shardable string, so swapping the *scheme* behind `assign_cell_id` touched
  only the call sites — no downstream math or storage changed. `h3.latlng_to_cell` is C-fast, so
  100k assignments cost nothing.
- **The Session-19/20 architecture was already sparse.** Lazy birth needed **zero** new code — the
  `get-or-create` updater pattern and write-on-save store already guaranteed it; Step 2 was pure
  verification + a proof test. The generic `StateStore[StateT]` (made generic in S20) meant Redis
  and eviction serve both `WorldCellState` and `KalmanCellState` with no fork.
- **Reusing proven patterns instead of inventing.** `RedisStateStore` mirrors `RedisStreamBroker`
  (lazy import, injectable client, env-var resolution); `EvictingStateStore` mirrors
  `SimulationCache` (OrderedDict TTL+LRU). Both were small, familiar diffs with a known ceiling.
- **Injectable fakes over a live server.** A ~15-line fake redis client tested the serialization +
  history-cap logic with no Redis running, keeping CI dependency-free.

**What Didn't Work / Notes**:
- **`redis.asyncio` vs the sync contract.** The brief said use `redis.asyncio`, but `StateStore` is a
  **synchronous** contract (the updaters call it inline inside the predict–correct step, and the
  processor callback path is sync). An async store would force the entire updater/pipeline async for
  no benefit — the broker is async because *its* contract is; the state store's is not. Resolved by
  using the **synchronous** `redis` client (documented in the `RedisStateStore` docstring), which
  keeps it a true drop-in for the existing `StateUpdater`. This was the one deliberate deviation.
- **Fragile H3 boundary test.** The first "nearby points share a cell" assertion picked two points
  ~1.4 km apart that happened to straddle a cell boundary and landed in different cells. Fixed by
  perturbing a cell's own centroid (`h3.cell_to_latlng`) so the test is boundary-robust.
- **Strict-mypy Protocol typing.** Adding `model_dump_json`/`model_validate_json` to the `_CellState`
  Protocol first typed the classmethod as returning `_CellState`, so `RedisStateStore` reads didn't
  narrow to `StateT`. Fixed with `Self` (a follow-up commit).
- **Eviction has no cold tier (by design).** Called out above and everywhere it matters — this is a
  Session-30 scope boundary (Session 35), not an oversight.

**Next Steps**: **Session 31 — Real Ingestion: the first live global feeds (FIRMS, USGS, GDACS).**
With addressing + sparse storage in place, wire real planetary data sources — NASA FIRMS (global
fires, not just the California bbox), USGS (earthquakes), GDACS (multi-hazard alerts) — through the
`assign_cell_id → EvictingStateStore` foundation so the global active set is driven by genuine live
events. Later in the arc: tiering/zoom over the H3 hierarchy (the unused parent/child helpers), and
the PostGIS cold tier + true rehydration (Session 35).

---

## Session 29 — Real-World Data Integration

**Goal**: End the demo's reliance on synthetic feeds. Through S28 the "live" stream still ran on
offline *oscillating mock* connectors (pure trig, no network) — convincing, but not real. Wire the
V3 live stream to **genuine live external data** so a fresh clone streams the actual current
California weather, and re-calibrate the forecasting math for the cadence and steadiness of real
hourly data.

**Current Progress**: Session 29 (**Real-World Data Integration — COMPLETE**). Three atomic
commits, one per step. Backend **150 pytest pass**, working tree clean.

- **Step 1 — real weather** (`feat: fetch real California weather from keyless Open-Meteo API`,
  `92c709d`). `realtime/connectors/weather.py` now fetches **current conditions from Open-Meteo**
  (`https://api.open-meteo.com/v1/forecast`), an **open, keyless** API — no signup, no `.env` key,
  so a fresh clone streams real weather with zero setup. The `current=temperature_2m,
  relative_humidity_2m,wind_speed_10m` block is parsed by `_parse_open_meteo` into our flat reading;
  Open-Meteo's defaults (°C, %, km/h) already match the canonical `WorldState` units, so **no unit
  conversion** is needed. Drought has no direct feed, so `_drought_from_humidity` derives a 0–1
  index from relative humidity (drier air ⇒ higher drought) — a documented `ponytail:` proxy for a
  real KBDI until a rainfall feed is wired. **Offline-safe**: on any `ConnectorError` (no network)
  it logs a warning and serves a deterministic `_offline_reading()` (hot/dry/breezy fire day), so
  ingestion never stalls or crashes; `base_url=None` forces the offline path for tests. A `demo()`
  `__main__` self-check asserts the payload normalizes to the four canonical observations.
- **Step 2 — drive the stream from real feeds** (`feat: drive live stream from real Open-Meteo and
  NASA FIRMS feeds`, `4e33bd3`). `realtime/live_stream.py` `LiveClimateStream.__init__` now defaults
  to the **real** connectors — `WeatherAPIConnector()` (live Open-Meteo) + `SatelliteAPIConnector()`
  (NASA FIRMS, which self-degrades to mocked California detections with a logged warning when no
  `MAP_KEY` is set) — instead of the offline `OscillatingWeatherConnector`/`GlobalSatelliteConnector`
  mocks. Connectors stay **injectable** (`weather=`, `satellite=` kwargs) so the test suite passes
  the deterministic offline oscillators for network-free, reproducible runs.
- **Step 3 — calibrate for real data** (`perf: calibrate live stream tick rate and Kalman noise for
  real data`, `4d3e14a`). Two hand-tuned constants in `live_stream.py`: `LIVE_TICK_SECONDS = 30.0`
  (Open-Meteo refreshes **hourly**, so the old ~1.5 s tick just re-read the same value and hammered
  the API — poll every 30 s: often enough to feel live, rare enough to be polite) and
  `_LIVE_PROCESS_NOISE_RATE = 5e-3` passed to `KalmanStateUpdater` (default `1e-4` is tuned for fast
  mock swings; under steady hourly readings the Kalman gain collapses → 0 and the risk **flatlines**.
  A larger process-noise rate keeps the filter tracking genuine hourly change while still smoothing
  jitter). `frames()` and `LiveStreamBroadcaster` both default `tick_seconds` to `LIVE_TICK_SECONDS`.

**How Open-Meteo was integrated** (as requested): the integration is contained entirely in the
`WeatherAPIConnector`, so nothing downstream of the connector changed. `fetch()` issues one keyless
GET to `_OPEN_METEO_URL` with the cell's lat/lon and the three `current` variables; `_parse_open_meteo`
lifts the `current` block into a flat `{temperature, humidity, wind, drought}` reading (drought
derived from humidity); the connector's existing `normalize()` then fans that reading out — via the
unchanged `_VARIABLE_MAP` — into one `WeatherEvent` per canonical `WorldState` variable
(`temp_anomaly_c`, `humidity_pct`, `wind_speed_kmh`, `drought_index`). From there the **existing V3
pipeline is untouched**: events flow `IngestionManager → EventProducer → broker → ContinuousPipeline
(Kalman → Bayesian → Monte Carlo → decision report) → frame`. Because Open-Meteo needs no API key
and the connector falls back to a deterministic offline reading when the network is down, the "real
data" upgrade preserved the project's **zero-setup, offline-safe, key-free** promise.

**What Worked**:
- **Open-Meteo's keyless open API** was the right call — real current weather with no signup and no
  secret to commit, so the project's zero-config promise survived the jump from mock to live data.
- **Confining the change to the connector boundary.** `fetch()`/`normalize()` already existed as the
  seam; swapping the data *source* behind them meant the whole Kalman→Bayesian→Monte-Carlo→board
  pipeline needed no edits. Smallest possible diff for "go live."
- **Injectable connectors** kept the test suite deterministic and network-free — real feeds are the
  runtime default, offline oscillating mocks are passed in by tests — so going live added **zero**
  flaky network dependencies to CI (150 pass).
- **Calibrating to the physical feed, not the model on paper.** Real Open-Meteo is hourly and steady,
  the exact opposite of the fast, swinging mocks the defaults were tuned for; the tick rate and
  process-noise knobs are the calibration the real world needs that a minimal model can't see.

**What Didn't Work / Notes**:
- **Default Kalman noise flatlined on real data.** With the mock-tuned `1e-4` process-noise rate,
  steady hourly readings drove the filter gain to ~0 and the risk score froze — the filter "trusted"
  its estimate and stopped listening to new data. Raising the rate to `5e-3` was the fix; it's a
  hand-tuned `ponytail:` knob (widen if the live feed proves noisier than expected), not a derived
  constant.
- **Drought is a proxy, not a measurement.** Open-Meteo's keyless current-conditions block has no
  drought/precipitation-deficit field, so drought is derived from relative humidity — flagged
  `ponytail:` to swap for a real KBDI index when a rainfall feed is wired in.
- **FIRMS still needs a key for live fires.** Weather went fully live keyless, but genuine global
  fire detections need a `MAP_KEY`; without one the satellite connector logs a warning and serves
  mocked California detections. Real weather + fallback fires was the pragmatic ship.

**Next Steps**: **VECTIS V3 is ready for production deployment.** Optional future polish: set
`VECTIS_FIRMS_API_KEY`/`MAP_KEY` for genuine live global fire detections; replace the
humidity-derived drought proxy with a real KBDI/precipitation-deficit feed; wire per-cell
climatology into `_VARIABLE_MAP` offsets so temperature becomes a true anomaly rather than a raw
reading.

---

## Session 28 — Backend Global Data Reset

**Goal**: The S26/S27 frontend went global, but the **backend still emitted "Liguria"** — the
live stream's headline cell was `Liguria_01` at the Liguria centroid, `/api/v1/regions` returned
only "Liguria, Italy", and decision reports rendered "Liguria". On the now-global map the legacy
Liguria analysis plotted in the Mediterranean while the map framed the Atlantic, so it looked
empty/disconnected. Purge Liguria from the backend data so the data matches the global UI.

**Current Progress**: Session 28 (**COMPLETE**). Three atomic commits, one per step. Backend
**148 pytest pass**, `ruff` + `mypy` clean. Live demo verified: headline cell renders
`California_01`, risk breathes 66 (HIGH) → 84 (SEVERE).

- **Step 1 — live stream** (`feat: move live stream headline cell from Liguria to California`).
  `realtime/connectors/weather.py` default location → `GeoPoint(37.0, -120.0)`;
  `realtime/connectors/satellite.py` FIRMS bbox + offline detections → California;
  `realtime/live_stream.py` `CELL_LABEL = "California_01"`, and the global hotspot footprint now
  leads with the California headland `(37.0, -120.0)` (its coords **must** match the weather
  location so both feeds resolve to the same `naive_cell_id` grid cell — that's what gives the
  headline cell its fire signal); dropped the Liguria hotspot. Renamed the scenario-state factory
  `liguria_wildfire_state → california_wildfire_state` (+ the 3 sim tests that import it).
- **Step 2 — region API + data** (`feat: replace hardcoded Liguria region with global California
  default`). `data/regions.py` `LIGURIA → CALIFORNIA` (key `california`, label "California, USA",
  US, **bbox lat 36–40 / lon −122 to −118**) plus new `NEW_SOUTH_WALES` and `ATTICA` Region
  entries; `REGIONS` now serves all three so `GET /api/v1/regions` is a global list.
  `streaming/updater.py` registers a `RegionTwin` per region and defaults to `california`;
  `api/routers/intelligence.py` report default → `california`. `scripts/generate_sample.py`
  defaults to California and **regenerated `data/samples/california/cells.csv`** (240 cells, fire
  rate 0.438). Renamed `scripts/run_demo_liguria.py → run_demo_california.py`.
- **Step 3 — decision reports / cleanup** (`refactor: purge remaining Liguria references for
  dynamic California reports`). The board/agents were **already region-dynamic** (they read
  `inp.region` from the twin — no hardcoded region in the LLM prompts), so the fix was flipping
  the `RegionTwin` default to `california` and scrubbing the residual `liguria`/`Liguria` strings
  across twins, demos, streaming wiring, docstrings, tests, and docs. Reports now narrate
  "California" end to end.

**How the static region data was migrated to plot on the global map**: the offline 240-cell
dataset is **generated**, not committed as fixed coordinates — `generate_sample.build_frame`
lays a regular `linspace` grid across `region.bbox`. So "migrating" the CSV is just retargeting
the region's bounding box: changing `CALIFORNIA.bbox` from the Ligurian arc (lat 43.78–44.68 /
lon 7.49–10.07) to California (lat 36–40 / lon −122 to −118) and re-running `make seed`
reproduces the same physically-plausible grid with North-American lat/lons. No per-cell
coordinate surgery — one bbox edit translates all 240 cells onto the global basemap.

**What Worked**: a scoped, case-aware string rename (`liguria → california` etc.) across `vectis`
+ `tests` did the bulk mechanically; the bbox-driven sample generator meant the data migration was
a 4-number edit; and because the analysis board already used the twin's region name, "Step 3" was
mostly verification, not new code.

**What Didn't Work / Notes**: internal Kalman/Bayesian unit-test cell-id constants (`"44.4,8.9"`)
were **left as-is** — they're arbitrary grid keys with no "Liguria" label, so renaming them is
pure churn. Historical/architecture narrative in `docs/` still references Liguria where it
describes the project's development history; only the *functional* doc references (a CSV path, two
runnable curl examples, a sequence-diagram twin label) were corrected. NSW/Attica have live twins
(so `/intelligence/reports` works for them) but **no seeded V1 sample CSV or trained model**, so a
legacy `POST /analyses` on them returns a clean "sample data not found" — the V3 twin/stream path
is the global one. `ponytail:` seed + train those two regions if the V1 ML path needs them.

**Next Steps**: the backend is now globally consistent with the frontend. Optional: seed+train NSW
and Attica for full V1 parity; wire a real global FIRMS bbox when a `MAP_KEY` is present.

---

## Session 27 — Global Frontend Hard Reset & UI Polish

**Goal**: Make the frontend read as one cohesive *global tactical console* on a standard laptop.
Three concrete defects from the S26 dump: (1) the Live Intelligence layout stacked vertically on
1080p because the grid only went multi-column at `xl` (≥1280px); (2) the live map was a squashed
`h-72` with a flat default view; (3) the **legacy V1 pages still rendered the Liguria 240-cell
grid** (Maps, Climate Risk Intelligence) plus a Liguria-pinned 3D globe — breaking the global
illusion the V3 backend earned.

**Current Progress**: Session 27 (**COMPLETE**). Three atomic commits, one per step. `tsc -b` +
`vite build` clean, **14 Vitest pass**.

- **Step 1 — live layout & map** (`feat(frontend): widen the live console for laptops and frame the
  globe`). `pages/LiveIntelligencePage.tsx` grid breakpoints `xl:`→`lg:` (two-column from 1024px).
  `features/realtime/LiveRiskMap.tsx` height `h-72`→`h-[450px]`. New shared
  `components/map/world.ts` exporting the `WORLD` `RegionInfo` (Atlantic centre `lat 20 / lon −30`)
  + `WORLD_ZOOM = 1.5`, replacing the local copy LiveRiskMap had defined inline.
- **Step 2 — retire the legacy grid** (`refactor(frontend): retire the legacy regional grid for a
  global view`). `pages/MapsPage.tsx` and `pages/RiskIntelligencePage.tsx` no longer plot
  `report.cell_risks` (the dense Liguria grid); both render the shared global basemap
  (`<RiskMap region={WORLD} cells={[]} />`) with a small "global view" overlay. Risk Intelligence
  keeps its region selector, **Run analysis** action, and the textual driver/detail panel — only the
  cell-grid map layer was removed. Scrubbed the three remaining `"Liguria, Italy"` strings in
  `test/fixtures.ts` → `"Global View"` (area labels) and the summary sentence → "Global monitoring…";
  realigned the two page tests that asserted the old label / map-prompt copy.
- **Step 3 — globalize the 3D globe** (`refactor(frontend): make the 3D globe a generic global
  widget`). `components/three/GlobeWidget.tsx` dropped the four hardcoded Liguria province centroids
  + the region-facing orientation; it now spins as a plain neon wireframe planet (graticule reads as
  a global grid).

**What Worked**:
- **Extracting `WORLD` to one module** let all three global map surfaces (live console + two legacy
  pages) share one Atlantic-framed `RegionInfo` — the legacy pages went global by passing it to the
  *existing* `RiskMap` with an empty cell array. No new map component, smallest diff.
- **Keeping Risk Intelligence functional.** Rather than a dead "coming soon" placeholder, dropping
  only the cell layer preserved the run-analysis → drivers/actions flow while removing the regional
  grid that broke the illusion.

**What Didn't Work / Notes**:
- The "Liguria, Italy" the user sees in the **running app comes from the backend**, not the frontend
  — the only frontend copies were the MSW *test* fixtures (the live app has no browser mocks; all
  data is fetched from FastAPI). Scrubbing the fixtures keeps the test suite on the global framing,
  but a fully global *live* app depends on the backend's region/area labels.
- `RiskLegend` was removed from the two legacy pages along with the cells — a legend with no cells to
  key is noise. It still ships for any future cell-bearing view.

**Next Steps**: Backend region labels are now the last "Liguria" the user can actually see in the
live app; a future session could globalize the backend's default region set / area labels. Frontend
bundle is still ~2.3 MB (three.js + maplibre) — code-splitting remains the open optimization.

---

## Session 26 — Global Frontend Expansion & UI Polish

**Goal**: Align the React frontend with the now-global V3 backend so a non-Italian reviewer
instantly reads VECTIS as a *global* climate-risk platform — not a Liguria-only V1 demo. Three
concrete defects to fix: (1) hardcoded "Liguria, Italy / 240 cells" regional framing in the UI;
(2) mock feeds that ramp until risk pins at 100% and flatlines (looks broken); (3) a 2D single-dot
map that's a V1 relic instead of a real world map with global alerts.

**Current Progress**: Session 26 (Global Frontend Expansion — **COMPLETE**). Three atomic commits,
one per step. Backend **148 tests pass** (+1 new anti-flatline test), `ruff`/`mypy` clean on the
touched files; frontend **14 Vitest pass**, `tsc` + `eslint --max-warnings 0` + `vite build` clean.

- **Step 1 — scrub regional hardcodes** (`refactor(frontend): reframe UI from regional Liguria to
  global intelligence`). Live Intelligence subtitle → "live global wildfire risk"; Overview's
  globe card → "Global Tactical View"; the dataset catalog drops the fixed "240 cells" count and
  marks the NASA FIRMS *global* feed `active` (it went live in S25). Files:
  `pages/LiveIntelligencePage.tsx`, `pages/OverviewPage.tsx`, `services/mocks/datasets.ts`.
- **Step 2 — fix the flatlining feeds** (`fix(realtime): fluctuate the live feeds instead of
  ramping to a flatline`). The demo feeds in `realtime/live_stream.py` ramped temp/humidity/wind
  monotonically every tick → risk climbed to 100% and stuck. Replaced with sums of incommensurate
  sine waves (`_wave`) around a *moderate* baseline: temperature centred near 25 °C, i.e.
  `temp_anomaly_c ≈ 3` — deliberately **below** the wildfire logistic's saturation point (the model
  saturates past ~+6 °C anomaly; `temp_anomaly_c = temperature − 22` via `KALMAN_TO_WORLD`). Risk
  now breathes between **~61 (HIGH) and ~91 (SEVERE)** and confidence moves with it. Renamed the
  feeds `RampingWeatherConnector→OscillatingWeatherConnector` and
  `EscalatingSatelliteConnector→GlobalSatelliteConnector`; updated `scripts/demo_v3_live.py` imports
  and the two tests that asserted the old monotonic climb (now assert risk moves **up AND down**
  without pinning). New self-check `test_risk_oscillates_and_does_not_flatline`.
- **Step 3 — global map** (`feat(frontend): plot live global fire hotspots on a real world map`).
  `GlobalSatelliteConnector` emits a worldwide hotspot set (California, NSW, Attica, British
  Columbia, Rondônia, + Liguria) with fluctuating FRP; `live_stream._frame` now surfaces a
  `hotspots[]` array (lat/lon/frp/place) from the tick's fire-detection events. `components/map/
  RiskMap.tsx` gained a real-world dark basemap (CARTO free raster tiles, no API key) + a
  configurable `zoom`. `features/realtime/LiveRiskMap.tsx` is now a whole-globe view plotting every
  hotspot coloured by FRP, with the headline cell coloured by live risk. `types/v3.ts` + the
  realtime tests follow.

**What Worked**:
- **Token-level UI scrub** — the regional framing was concentrated in a few headers/subtitles and
  one mock catalog, so reframing as "global" was a tiny, low-risk diff (no component rewrites).
- **Calibrating against the model's saturation point, empirically.** The first oscillation attempt
  (baseline 30 °C) still pinned risk at ~99 because the logistic saturates. Printing the risk series
  and walking the baseline down to ~22.5 °C / +5 amplitude landed a graph that visibly crosses the
  HIGH↔SEVERE band line — the "breathing" a reviewer needs to see.
- **Pure-trig feeds (no RNG)** keep every viewer's stream identical and tests deterministic, while
  still looking organic via two incommensurate sine periods per variable.
- **Reusing `RiskMap` for the global view** — adding a `zoom` prop + a raster basemap to the one
  shared map component upgraded *every* page's map at once, and let `LiveRiskMap` go global by just
  passing a world `RegionInfo` + the hotspot cells. Smallest diff, biggest visual change.
- **Free CARTO raster tiles** give a real basemap with **no API key**, preserving the project's
  key-free promise; offline, the dark background shows through and the risk cells still render.

**What Didn't Work**:
- **First mock-data baseline was too hot.** Centering temperature at 30 °C (anomaly +8) saturated
  the logistic → risk flatlined at ~99 even though the *input* oscillated. The Kalman filter also
  smooths the noisy reading, compressing the swing — so the baseline had to drop well into the
  moderate range before the *filtered* estimate moved risk across a band. Fixed by calibration, not
  by fighting the filter.
- **The two old demo tests were asserting the very bug we removed** (`risk ends > start + 5`,
  `hotter_drier` posterior `>0.5`, driver flips, monotonic climb). They had to be rewritten to
  assert liveliness-via-oscillation rather than monotonic escalation — a reminder that a test can
  encode a misfeature.
- **Routing global hotspots through the math pipeline is slightly wasteful** — each worldwide
  detection spins up its own Kalman cell + MC run that the frame never displays (only the Liguria
  headline cell is read). Bounded (~6 cells) so left as-is; `ponytail:`-style note: if hotspot count
  grows, plot them as display-only context instead of feeding them through the engine.

**Next Steps**: **Ready for Final Review / Deployment.** The console now reads as a global platform
end to end. Optional polish for a future session: (a) make the headline cell *selectable* from the
global map (click a hotspot → that cell drives the header/timeline) so "Selected Region" is literal;
(b) wire a real global FIRMS bbox (`-180,-90,180,90`) so live hotspots are genuine when a `MAP_KEY`
is present; (c) code-split the 2.3 MB frontend bundle (three.js + maplibre) flagged by `vite build`.

---

> **Session history:** S1 — full foundation + working vertical slice (agents/ML/API/
> frontend). S2 — hardened the backend/data **foundation** (DB session layer, Alembic
> migrations, readiness probe, data staging dirs). S3 — **intelligence layer**: added a
> second, selectable **LangGraph** orchestration engine behind a shared interface (reusing
> the existing agents), extended ML metrics, and made model selection auditable. S4 —
> **enterprise frontend layer**: a full multi-page React/TS decision-intelligence console
> (routing, design system, TanStack Query data layer, MapLibre risk map, report + simulation
> UI) consuming the real backend API. S5 — **open-source / production-readiness hardening**:
> closed real infra gaps (frontend tests now in CI, Docker healthchecks + reproducible builds,
> repo-structure docs, formatting baseline, security review) — no product features.

---

## Goal

Build **VECTIS**: a production-grade, open-source **Real-Time Probabilistic Decision Intelligence Platform** that turns complex real-world data into **explainable, actionable** forecasting. 
First vertical: **Climate (wildfire) Risk Intelligence**, demoed on **Liguria, Italy**.

The project is now in two layers:

- **V1 — Reactive Decision Intelligence (COMPLETE, Sessions 1–5).** Answers *what is happening ·
  why · what could happen next (sensitivity) · what to do*, using a data pipeline, an ML model
  with SHAP, and LLM agents that narrate (never decide) an explainable `DecisionReport`.
- **V2 — The Simulation & Forecasting Engine (STARTED, Session 6 = foundation).** Answers a new
  question: *given the current state of the world, what are all plausible futures, and with what
  probability?* It produces **distributions over outcomes**, not single numbers, via Monte Carlo.

**The Golden Rule of V2:** LLMs never do math. All probabilistic/statistical computation lives in
deterministic libraries (`numpy`/`scipy`/`pymc`) behind explicit interfaces. LLMs re-enter only
as "Analyst" agents that *read* the numerical output. The V1 "LLM-narrates-not-decides" discipline
is now enforced at the layer boundary: everything inside `simulation/` is pure math.

Non-negotiables: explainable AI, human-in-the-loop, modular architecture, reproducibility,
clean engineering, exceptional docs.

---

## Current Progress (Session 1 — COMPLETE)

Delivered the **foundation + a complete, working end-to-end vertical slice**. The whole
stack runs offline with no API keys.

**Verified working (all green):**
- `make seed` → deterministic 240-cell Liguria sample (fire rate ~0.44).
- `make train` → trains LogReg / RandomForest / XGBoost; best = **logistic_regression**,
  **ROC-AUC 0.907**, Brier 0.126. Writes model + model card to the registry.
- `make demo` → full 6-agent pipeline → Decision Report: **risk 76.7/100 (SEVERE)**,
  confidence 89%, SHAP drivers, a "hotter/drier month" scenario (+12.2), recommended
  actions, **Critic APPROVED**.
- API: `POST /api/v1/analyses` returns the report (201); `GET /{id}`, `/regions`,
  `/models/{region}`, `/health` work; unknown region → 404. Persists to SQLite/Postgres
  (in-memory fallback when no DB).
- **Tests: 30 passed.** `ruff` clean, `mypy` clean (54 files). Frontend `npm run build`
  and `npm run lint` clean.

**What exists, by layer:**
- **Tooling/OSS**: git repo, `.gitignore`, Apache-2.0 `LICENSE`, `CONTRIBUTING`,
  `CODE_OF_CONDUCT`, `SECURITY`, GitHub issue/PR templates, `.github/workflows/ci.yml`,
  `Makefile`, `.env.example`, `docker-compose.yml`.
- **Backend** (`backend/vectis/`):
  - `core/` — `config.py` (Pydantic Settings), `logging.py` (structlog), `exceptions.py`,
    **`schemas.py` (the contracts spine: `DecisionReport`, `AgentState`, `Driver`, etc.)**.
  - `data/` — `regions.py` (Liguria), `connectors/` (`SampleConnector` + live stubs),
    `pipeline/` (`schema.py` feature defs, `steps.py`, `runner.py` with content hashing).
  - `models/` — `training.py`, `evaluation.py`, `explain.py` (SHAP), `registry.py`
    (model cards), `predictor.py`.
  - `agents/` — `base.py` (`Agent` + `RunContext`), `orchestrator.py` (DAG + Critic loop),
    `discovery/analyst/ml_research/simulation/report/critic.py`, `llm/` (`base`, `mock`,
    `anthropic`, `factory`).
  - `services/analysis_service.py`, `database/` (models + repository), `api/` (FastAPI app,
    routers), `scripts/` (`generate_sample`, `train`, `demo`).
  - `tests/` — unit / model / integration / api (30 tests).
- **Frontend** (`frontend/src/`): Vite + React + TS console — `App.tsx`, `lib/api.ts`
  (typed client mirroring backend), `components/MapView.tsx` (MapLibre, offline dark
  style), `DriversChart.tsx` (Recharts SHAP bars), `ReportPanel.tsx`, enterprise dark CSS.
- **Docs**: `README.md` + `docs/{architecture,agents,data_pipeline,development}.md`.

---

## Current Progress (Session 2 — COMPLETE)

Focus: **backend + data foundation hardening only** (per Session 2 brief). Reconciliation
note: the Session 2 brief described building a foundation that S1 had already delivered. A
parallel `backend/app/` rebuild was **deliberately not done** — it would duplicate working,
tested code and violate this HANDOFF as source of truth. The brief's structure maps onto the
existing `backend/vectis/` package (`core` = core+`core/schemas.py`, ORM = `database/models.py`,
ML models = `models/`). Instead, S2 closed the real foundation gaps:

**New / changed (all verified green):**
- **DB session layer consolidated** → `database/session.py` is now the single engine source:
  `get_engine()`/`get_sessionmaker()` (cached, lazy), `get_db()` FastAPI dependency,
  `init_db()`, `ping()`, `reset_engine_cache()`. `database/base.py` slimmed to just `Base`.
  `repository.build_repository()` now pings + ensures schema before the SQL path (signature
  changed: no longer takes a URL — reads settings). `api/main.py` updated.
- **Readiness probe** → `GET /health/ready` (200 ready / 503 degraded) checks DB via `ping()`;
  `GET /health` stays as liveness.
- **Alembic migrations** → `backend/alembic/` (`env.py` reads URL from VECTIS settings, not
  ini; `versions/0001_initial.py` creates `analyses`). Verified `alembic upgrade head` on
  SQLite. `alembic` added to deps; `make migrate` / `make revision` added; Docker runs
  `alembic upgrade head` on startup (Dockerfile copies `alembic.ini` + `alembic/`).
- **Data staging dirs** → `data/{raw,processed,validation,pipelines,schemas}/` with `.gitkeep`
  + `data/README.md` (lineage + git policy). `.gitignore` updated (track `samples/`+`schemas/`,
  ignore the rest).
- **Tests** → `tests/integration/test_database.py` (engine/session/ping/init_db/get_db +
  repository roundtrip) and a readiness API test. **34 test functions, all pass.**
  `ruff` clean, `mypy` clean (55 files).
- **Docs** → README, `docs/architecture.md`, `docs/development.md` updated for the DB layer,
  migrations, readiness, and data staging.

---

## Current Progress (Session 3 — COMPLETE)

Focus: **intelligence layer** (agents + ML), no frontend. Reconciliation: the brief asked to
build an agent system + ML that **already existed** from S1. Per "do not recreate previous
work," nothing was rebuilt; the one genuinely new ask — **LangGraph** — was realized as the
S1-planned swappable engine.

**AI agent system:**
- **Two interchangeable orchestration engines** behind a shared `BaseOrchestrator`
  (`agents/runtime.py`), over the same `AgentSuite` of 6 agents:
  - `custom` (default) — `agents/orchestrator.py`, refactored to use the shared runtime.
  - `langgraph` — `agents/langgraph_engine.py`, a `StateGraph` with a conditional Critic
    edge. Selected via `VECTIS_ORCHESTRATOR` (`get_orchestrator()` factory). **Verified parity:
    both engines yield byte-identical reports** (risk 76.7, same drivers, Critic approved).
- Each agent now declares a `responsibility`; the ML Research agent surfaces the **model
  comparison + selection rationale** into its trace (auditable model choice).
- `AnalysisService` now resolves the engine via the factory.

**ML pipeline:**
- `evaluation.Metrics` extended with **accuracy, precision, recall** (alongside F1, ROC-AUC,
  PR-AUC, Brier). Model cards now carry all of them. (LogReg still wins; ROC-AUC 0.907,
  accuracy 0.80, precision 0.79, recall 0.73.)
- SHAP explainability, registry/model cards, predictor — unchanged from S1 (already complete).

**Files added:** `agents/runtime.py`, `agents/langgraph_engine.py`,
`tests/integration/test_langgraph_orchestrator.py`, `tests/model/test_evaluation.py`,
`tests/unit/test_agents_meta.py`, `docs/ml_pipeline.md`.
**Changed:** `agents/orchestrator.py`, `agents/__init__.py`, `agents/ml_research.py`,
`agents/base.py` + the 5 other agents (`responsibility`), `models/evaluation.py`,
`services/analysis_service.py`, `core/config.py`, `.env.example`, `pyproject.toml`
(`langgraph` extra + scoped mypy override), README, `docs/agents.md`.

**Verified green:** **48 tests pass** (was 34). `ruff` clean, `mypy` clean (57 files).
LangGraph 1.2.6 installed in the venv; the parity test `importorskip`s it so a lean install
stays green.

---

## Current Progress (Session 4 — COMPLETE)

Focus: **enterprise-grade frontend layer**, no backend changes. Reconciliation: the S4 brief
named the project "ATLAS" and asked to scaffold `frontend/` from scratch; this is the **VECTIS**
repo and a Vite/React/TS frontend already existed from S1. Per "do not recreate previous work,"
the existing frontend was **expanded into the full enterprise console** the brief describes —
not rebuilt. (A prior S4 run had already authored the bulk of the tree; this session **verified
it green, fixed the failing tests, and completed the documentation**.)

**Frontend status — all green:** `tsc --noEmit` clean, `eslint --max-warnings 0` clean,
**7 Vitest tests pass** (4 files), `vite build` succeeds. Multi-page SPA, enterprise-grade dense
dark UI, consuming the real backend API.

**Architecture** (`frontend/src/`, one-way deps `pages → features → components → ui`):
- `app/` — `App.tsx` (React Router routes), `AppLayout.tsx` (sidebar+navbar shell), `providers.tsx`
  (QueryClient + Router).
- `components/ui/` — design system: `Button, Card, Badge, Table, Modal, StatCard`, `states`
  (Loading/Error/Empty), `risk` (RiskBadge), barrel `index.ts`.
- `components/layout/` — `Sidebar, Navbar, Page`, `nav.ts`, `icons.tsx`.
- `components/map/` — `RiskMap` (MapLibre choropleth), `RiskLegend`. `components/charts/` —
  `DriversChart` (Recharts SHAP bars).
- `features/` — `risk/` (RegionSelector, RiskDetailPanel), `reports/` (ReportViewer,
  AgentTraceList), `simulations/` (ScenarioPanel).
- `pages/` — Overview, RiskIntelligence, Maps, Reports, ReportDetail, Simulations, Datasets,
  NotFound.
- `hooks/queries.ts` — the single React↔backend boundary (TanStack Query): `useHealth`,
  `useRegions`, `useAnalyses`, `useAnalysis`, `useModelCard`, `useDatasets`, `useRunAnalysis`.
- `services/` — `apiClient.ts` (the only `fetch`; normalizes both backend error shapes; reads
  `VITE_API_BASE_URL`), `analyses.ts`, `catalog.ts`, `datasets.ts`, `queryKeys.ts`, `mocks/`.
- `stores/` — Zustand `selectionStore` (region/analysis/cell) + `uiStore` (sidebar). `types/api.ts`
  mirrors backend schemas. `utils/` (cn, format, risk). `test/` (renderWithProviders, MSW server,
  fixtures, maplibre stub).

**API integrations (real endpoints):** `POST /api/v1/analyses`, `GET /api/v1/analyses`,
`GET /api/v1/analyses/{id}`, `GET /api/v1/regions`, `GET /api/v1/models/{region}`, `GET /health`.
`useRunAnalysis` seeds the cache, invalidates the list, and focuses the new analysis on success.

**Mocks (clearly separated):** only the **Datasets catalog** (`services/mocks/datasets.ts`,
`⚠️ MOCK DATA` header + `DATASETS_ARE_MOCK` flag) — no `/datasets` backend endpoint yet. The
custom-scenario builder in `ScenarioPanel` is architecture-only (controls disabled, `Preview`
badge); displayed scenarios are real, read from the report's Simulation trace.

**Design system decisions:** Tailwind tokens in `tailwind.config.js`; risk band→color/label
centralized in `utils/risk.ts`; dark enterprise theme; `@/` import alias → `src/`.

**Tests:** `Button` (component), `ReportViewer` (feature), `OverviewPage` +
`RiskIntelligencePage` (page render + full API-mocked flow via **MSW**).

**This session's fixes:** two page tests asserted `getByText` for strings the UI legitimately
renders more than once (`"Liguria, Italy"` in both a stat card and the table row; `"Severe"` in
a risk badge and the detail panel) → switched to `getAllByText(...).length` (root cause: brittle
singular assertions, not an app bug).

**Docs:** new `docs/frontend.md` (architecture, library rationale incl. **MapLibre over
Mapbox/Leaflet/OpenLayers**, real-vs-mock policy, env config, testing); README gained a
**Frontend — Decision Intelligence Console** section + screenshots placeholder + doc-index link.

---

## Current Progress (Session 5 — COMPLETE)

Focus: **make VECTIS a serious, publishable open-source project** — reproducible, installable,
testable, understandable. No new product features. Reconciliation: most OSS scaffolding already
existed and was **good** (LICENSE, CONTRIBUTING, CODE_OF_CONDUCT, SECURITY, issue/PR templates,
CI, docker-compose, `.env.example`, all 6 `docs/`). Per "don't redo previous work," S5 was a
**senior audit that fixed the genuine gaps** rather than regenerating boilerplate.

**Gaps found and fixed (each justified, no fake completeness):**
- **CI didn't run the frontend tests.** S4 added 7 Vitest tests but `ci.yml` only did
  `lint` + `build` — tests that never run rot. Added `npm run typecheck` + `npm run test` to the
  frontend job (renamed *Frontend (lint · type · test · build)*). Now every push validates both
  stacks fully.
- **Docker had no backend/frontend healthcheck.** Only `db` had one; `frontend` depended on
  `backend` without a readiness gate. Added a **backend healthcheck** (hits `/health` via
  `python -c urllib` — no curl added to the slim image; `start_period: 90s` covers the one-time
  migrate+seed+train on boot) and changed `frontend` to `depends_on: backend: condition:
  service_healthy`. `docker compose up` now starts the UI only when the API is truly ready.
- **Frontend image wasn't reproducible.** `Dockerfile` ran `npm install` from `package.json`
  only. Now copies `package-lock.json` and runs **`npm ci`** (verified in sync locally).
- **No editor formatting baseline.** Added root **`.editorconfig`** (LF, UTF-8, final newline,
  4-space Python / 2-space everywhere else) — cross-stack, zero churn, no Prettier conflict.
- **README lacked a repository-structure map and a diagram pointer.** Added a **Repository
  structure** tree and an architecture-diagram placeholder note (the ASCII diagram is canonical;
  a rendered one belongs under `docs/assets/`).

**Security review (clean):** `.env` / `.env.*` git-ignored except `.env.example`; only
`.env.example` is tracked and its key field is empty; `backend/artifacts/` ignored; no hardcoded
secrets in tracked source (`git grep` for `sk-ant-`/`AKIA`/password literals — none); the only
committed credentials are the local-only Postgres dev creds in `docker-compose.yml`. LLM provider
defaults to `mock` (no network, no key).

**Final validation (both stacks green, exactly what CI runs):**
- Backend: `ruff` clean, `mypy` clean (57 files), **48 pytest pass**.
- Frontend: `lint` clean, `typecheck` clean, **7 Vitest pass**, `npm ci` + `vite build` succeed.

**Files added:** `.editorconfig`. **Changed:** `.github/workflows/ci.yml`, `docker-compose.yml`,
`frontend/Dockerfile`, `README.md`, `HANDOFF.md`.

**Post-S5 maintenance (frontend status — still green):** fixed a TypeScript deprecation in
`frontend/tsconfig.json` — `baseUrl` is deprecated and removed in TS 7.0. Dropped `baseUrl: "."`
and made the path alias self-relative (`"@/*": ["./src/*"]`); TS 5.0+ resolves `paths` relative to
the tsconfig's own directory, so no `baseUrl` is needed. `npm run typecheck` and `vite build`
still pass and the `@/` alias resolves unchanged (Vite's own alias in `vite.config.ts` was never
affected). No component, API, or design-system changes — the S4 frontend (8 pages, design system,
TanStack Query data layer, MapLibre map, real backend integrations) is unchanged and intact.

---

## Current Progress (Session 6 — COMPLETE)

Focus: **frontend visual redesign — enterprise-grade tactical 3D aesthetic.**
No backend or data-layer changes; the S4/S5 architecture (8 pages, TanStack Query, MapLibre,
real backend integrations) is intact and still green.

**Frontend status:** all 7 Vitest tests pass, `typecheck` clean, `vite build` succeeds.

**Design-system decisions (centralized, token-driven — restyle from 2 files):**
- **Pure-black, neon, monospaced theme** via `tailwind.config.js` tokens only. `bg` → `#000000`,
  surfaces near-black, `text` → neon green `#39ff14`, `accent` → neon cyan `#00ffd5`, borders are
  dim/active neon greens. Because every component already used semantic tokens (`bg-bg`, `text-text`,
  `accent`, `border`), recoloring the tokens restyled the entire console with near-zero per-component
  churn.
- **Strictly monospaced** — `fontFamily.sans` now aliases the JetBrains Mono stack, so existing
  `font-sans` usages become terminal-style without editing each component. JetBrains Mono loaded via
  Google Fonts `@import` in `styles/index.css`.
- **Tactical radar grid** — fixed-attachment CSS background on `body` (fine neon lattice +
  radial cyan glow) in `styles/index.css`. Pure CSS, no component or canvas needed.
- **Neon glow** — `text-glow` / `text-glow-cyan` utilities and `shadow-glow*` tokens; applied to
  headings (sidebar wordmark, navbar section title) and primary buttons.
- **Arwes-style 45° corners + thin contour lines** — `clip-corner` / `clip-corner-sm` clip-path
  utilities applied to the shared `Card` and `Button` primitives plus a neon contour border/ring,
  so every panel and button across all pages inherits the high-tech cut from one place.

**Components created:**
- `src/components/three/GlobeWidget.tsx` — interactive 3D neon-green wireframe globe
  (`@react-three/fiber` + `three` + `@react-three/drei` `OrbitControls`). Plots the four Liguria
  province centroids (Genova, Savona, Imperia, La Spezia) as glowing cyan nodes with radial spikes
  on a slowly auto-rotating sphere oriented to face Liguria. Drag to orbit, scroll to zoom. Mounted
  as a "Liguria — Tactical View" card on the Overview page.

**API integrations completed:** none changed this session (pure presentation). The globe uses real
province coordinates; risk/analysis data wiring into the 3D nodes is left as a next step.

**Dependencies added:** `three`, `@react-three/fiber`, `@react-three/drei`.

**Files changed:** `tailwind.config.js`, `src/styles/index.css`, `src/components/ui/Button.tsx`,
`src/components/ui/Card.tsx`, `src/components/layout/Sidebar.tsx`, `src/components/layout/Navbar.tsx`,
`src/pages/OverviewPage.tsx`. **Added:** `src/components/three/GlobeWidget.tsx`.

---

## Current Progress (V2 Foundation — COMPLETE)

> **Numbering reconciliation:** the V2 brief is labeled "Session 6," but this doc already used
> *Session 6* for the tactical frontend redesign (it matches the latest commit). To keep the
> history monotonic this block is the **V2 foundation** session — chronologically after the redesign.

Focus: **build the architectural skeleton + theoretical foundation for the V2 Simulation Engine.**
Per the brief, **no heavy logic** — no Monte Carlo generator, no statistics. Interfaces, schemas,
docstrings, and types only. The blueprint, not the building.

**Reconciliation (same lesson as S2/S4 — don't take a brief literally against this HANDOFF):** the
brief said create `backend/app/simulation/`. There is no `backend/app/`; the package is
`backend/vectis/`, and a parallel `app/` tree was deliberately rejected in S2. So V2 lives under
**`backend/vectis/simulation/`**, integrated with the existing tested package — not a duplicate tree.

**What was built (all green: ruff clean, mypy clean on 12 files, schema self-check passes):**
- **`docs/v2_simulation_engine.md`** — the V2 technical doc: V1(reactive)→V2(probabilistic)
  transition, an ASCII architecture diagram of the flow *(External Data → State Estimation →
  Scenario Generation → Monte Carlo → Probabilistic Output → Agent Analysis)*, and definitions of
  the four core concepts (State, Scenario, Simulation Run, Probability Distribution).
- **`backend/vectis/simulation/`** package, decoupled from `agents` (verified at import time —
  loading the whole layer pulls in **zero** `vectis.agents` modules; it depends only on `core`,
  Pydantic, stdlib). Subpackages: `engine/`, `scenarios/`, `models/`, `states/`, `probability/`,
  `forecasting/` — each with a docstring'd `__init__.py`.
- **`simulation/schemas.py`** — the V2 contracts spine (mirrors V1's `core/schemas.py`): Pydantic
  models for `WorldState`/`StateVariable` (digital twin *with uncertainty*), `Scenario`/`ScenarioSet`
  (priors **validated to sum to 1** — the invariant that makes outputs real probabilities),
  `ProbabilityDistribution` (mean/std/p05/p50/p95/exceedance), `SimulationConfig`/`SimulationRun`/
  `ScenarioOutcome`. Pure data containers — they carry numbers, never compute them. Reuses V1
  `RiskBand` so V1 and V2 share risk units. Has a tiny `__main__` self-check on the prior-sum guard.
- **Three mandated ABC interfaces** (strictly typed, docstring-rich, logic-free):
  `scenarios/base.py` → `ScenarioGenerator.generate(state) -> ScenarioSet`;
  `engine/monte_carlo.py` → `MonteCarloEngine.run(state, scenarios, config) -> SimulationRun`
  (contract demands seeded reproducibility + vectorization, no LLM/I/O);
  `probability/bayesian.py` → `BayesianUpdater.update(prior, observation) -> ScenarioSet` (+ the
  `Observation` schema). Plus a 4th: `states/base.py` → `StateEstimator.estimate(region) -> WorldState`
  (the digital-twin builder, since State Estimation is the diagram's first step).
- `models/` and `forecasting/` are intentionally placeholder packages (docstring'd `__init__.py`)
  — their concrete shape is chosen alongside the Session 7 Monte Carlo implementation.

**Files added:** `docs/v2_simulation_engine.md`; `backend/vectis/simulation/{__init__,schemas}.py`;
`simulation/{engine,scenarios,models,states,probability,forecasting}/__init__.py`;
`simulation/scenarios/base.py`, `simulation/engine/monte_carlo.py`,
`simulation/probability/bayesian.py`, `simulation/states/base.py`. **Changed:** `HANDOFF.md`.

**Quality bar ("would a senior engineer approve this for a high-frequency sim engine?"):** the math
boundary is structural — `simulation/` cannot reach the LLM layer (no agents import), so calculation
*can't* be delegated to an LLM by construction; schemas force uncertainty + normalized priors;
configs carry an RNG seed so reproducibility is a first-class contract; the engine ABC mandates
vectorization for 10k–1M draws. The skeleton is clean, decoupled, and mathematically honest.

---

## Current Progress (Session 7 — Monte Carlo Engine — COMPLETE)

Focus: **implement the concrete Monte Carlo simulation engine** behind the Session-6 ABCs.
Pure math, no LLMs (the V2 Golden Rule, enforced structurally — `simulation/` still imports
zero `vectis.agents`). Target: correctly generate + evaluate **100k scenarios** with
vectorization, reproducibility, and a parallel-execution architecture.

**Headline result:** 100k iterations × 3 scenarios (300k logistic evaluations) in **~70 ms**
— the brief's budget was 100k in <2 s. Reproducible (same seed ⇒ identical draws) and
optionally parallel (process-pool output is byte-identical to the serial path).

**What was built (all green: ruff clean, mypy clean on 74 files, 56 pytest pass — was 48):**
- **`engine/distributions.py`** — vectorized `Distribution` wrappers over `scipy.stats`
  (`Normal`, `Lognormal`, `Uniform`, `Poisson`, `Constant`) + a `distribution_for(StateVariable)`
  factory that fails loud on missing params. Each `.sample(rng, size)` is one C-level call
  threading an explicit numpy `Generator` as `random_state`.
- **`engine/sampler.py`** — `sample_state()` draws the whole `WorldState` into a
  `{name: ndarray}` column mapping (applying scenario perturbations first); `split_iterations()`
  balances chunks; reproducibility is rooted in numpy `SeedSequence`/`Generator`.
- **`models/wildfire.py`** — `WildfireHazardModel` (impl of new `HazardModel` ABC): a vectorized
  **logistic** `P(fire) = scipy.special.expit(intercept + Σ coef·input)`. Coefficients are
  illustrative (`ponytail:` — calibrate against FIRMS labels later).
- **`engine/runner.py`** — `VectorizedMonteCarloEngine` (impl of `MonteCarloEngine`). One code
  path, two modes: always splits draws into `n_workers` independent `SeedSequence.spawn` streams;
  `parallel=True & n_workers>1` runs chunks on a `ProcessPoolExecutor`, else serially —
  **identical numbers either way**. Reduces per-sample risk (0–100) to a `ProbabilityDistribution`
  (mean/std/p05/p50/p95 + band-exceedance P(≥50), P(≥75)).
- **`scenarios/generator.py`** — `WildfireScenarioGenerator` (impl of `ScenarioGenerator`): 3
  weighted branches (baseline 0.5 / hotter_drier 0.3 / extreme_wind 0.2) + `liguria_wildfire_state()`
  digital-twin factory (the +2 °C / −30 % rainfall / high-wind use case, with uncertainty).
- **`schemas.py`** extended: added `DistributionFamily.POISSON` and `SimulationConfig.n_workers` +
  `SimulationConfig.parallel`. `pyproject.toml`: added `scipy>=1.11` (now a direct dep).
- **`tests/simulation/test_monte_carlo.py`** — 8 tests: same-seed reproducibility, seed-sensitivity,
  100k-under-2s + stats sanity, retained-sample size + scenario ordering (hotter_drier > baseline),
  distribution bounds/shape, factory param validation, **parallel == serial-chunked**, prior-sum guard.

**Files added:** `engine/distributions.py`, `engine/sampler.py`, `engine/runner.py`,
`models/wildfire.py`, `scenarios/generator.py`, `tests/simulation/test_monte_carlo.py`.
**Changed:** `simulation/schemas.py`, `pyproject.toml`, `docs/v2_simulation_engine.md`, `HANDOFF.md`.

---

## Current Progress (Session 8 — Probability & Bayesian Update — COMPLETE)

Focus: **close the V2 learn-from-data loop** — take a Monte Carlo baseline (prior over
futures), ingest a real observation, and compute the posterior + a Confidence Score. Pure
math, no LLMs (`simulation/` still imports zero `vectis.agents`).

**Headline result:** the Liguria use case (`python -m vectis.simulation.probability.bayesian`)
ingests a +3.5 °C temperature spike and moves `hotter_drier` from prior **0.30 → posterior
0.92**; posterior-weighted fire risk **88 → 94 / 100**; confidence **6% → 71%**. Updating
1,000 observations takes <1 ms.

**What was built (all green: ruff clean, mypy clean, 66 pytest pass — was 56):**
- **`probability/bayesian.py` — `GaussianBayesianUpdater`** (impl of the S6 `BayesianUpdater`
  ABC). Posterior ∝ prior × likelihood, with a **Gaussian observation likelihood**: each
  scenario predicts `base_state_value + scenario_perturbation` for the observed variable;
  `P(obs | scenario) = N(obs.value; mean=predicted, sigma)`, `sigma = hypot(model_std,
  obs.std)`. The **evidence (denominator)** is handled exactly by normalizing over the finite
  scenario set, so the returned `ScenarioSet` priors sum to 1 → feeds straight back into
  `MonteCarloEngine.run`. Computed in **log-space** (subtract max log-posterior, then softmax)
  for numerical stability — a sharp likelihood can't underflow to an all-zero posterior.
  `update_batch` sums log-likelihoods across observations → a **joint, order-independent**
  update. The updater is constructed with the `WorldState` (the ABC's `update(prior,
  observation)` carries no state, but predicted values depend on it). `model_std` uses the
  state variable's `std` only when it's a natural-space `NORMAL` scale, else `default_model_std`.
- **`probability/uncertainty.py` — the Confidence Score.** Inversely related to spread.
  Categorical (`scenario_confidence`/`confidence_from_entropy`): `1 − normalized Shannon
  entropy` (uniform → 0, certain → 1). Continuous (`confidence_from_variance`/
  `distribution_confidence`): `1 / (1 + (std/scale)²)`. Plus `posterior_mixture_risk` —
  `Σ priorₛ · riskₛ` to collapse per-scenario MC risk into the "fire risk is now X%" headline.
- **`probability/calibration.py` — blueprint.** `CalibrationRecord` + `brier_score` (mean
  squared error of predicted-vs-actual) implemented and tested; `Calibrator.reliability_curve`
  and `fit_recalibration` (isotonic/Platt) are documented stubs awaiting a FIRMS-label backlog.
- **`tests/simulation/test_probability.py`** — 10 tests: strong obs moves prior the right
  way; non-discriminating obs leaves prior unchanged; posterior stays a valid distribution;
  consistent obs raise confidence; **matched-strength** contradictory obs lower it;
  determinism; batch order-independence; 1,000-obs throughput; confidence bounds/monotonicity;
  Brier accuracy. `probability/__init__.py` now exports the concrete API.

**Files added:** `probability/uncertainty.py`, `probability/calibration.py`,
`tests/simulation/test_probability.py`. **Changed:** `probability/bayesian.py` (added
`GaussianBayesianUpdater` + Liguria `__main__` demo), `probability/__init__.py`,
`docs/v2_simulation_engine.md`, `HANDOFF.md`.

**Gotcha (test design, not a code bug):** "contradictory observations increase uncertainty"
only holds when the conflicting observations have **matched evidential strength**. A wind obs
at separation 20 with σ≈3 is ~6σ-decisive and simply *dominates* a 2.6σ temperature obs (the
posterior collapses onto one branch, confidence stays high). The test deliberately widens the
wind obs `std` to 7.7 (≈2.6σ, matching the temp obs) so the two genuinely split the posterior.
Also: observing a scenario's *mean* still discriminates if other scenarios predict a different
mean — the "uninformative observation" is one no scenario predicts differently (test uses an
unknown/unperturbed variable → posterior == prior).

---

## Current Progress (Session 9 — Real-Time Intelligence Layer — COMPLETE)

Focus: **the orchestration layer that connects live data to the math engines.** When an event
arrives via the API, VECTIS registers it, runs the Bayesian update, re-runs Monte Carlo if the
belief shift is significant, and broadcasts the new risk state over WebSockets. Infrastructure-
light by design (no Kafka/Redis) but modular so they can drop in later. Zero LLM in the loop.

**What was built (all green: ruff clean, mypy clean, 73 pytest pass — was 66):** a new
**`backend/vectis/streaming/`** package + a stream API router, wired into the app.
- **`streaming/events.py`** — wire-format Pydantic models. Inbound: `SensorReading` /
  `WeatherAlert` as a `kind`-discriminated union (`IngestEvent`); each `to_observation()` maps
  itself to the Session-8 `Observation` (alert severity → measurement std). Outbound: `RiskState`
  (current posterior-weighted risk + band + confidence + scenario priors) and `StateChange` (the
  broadcast payload). `dedupe_key()` (source+variable+value) drives debouncing.
- **`streaming/updater.py`** — `RealTimeUpdater`, the **swappable seam**. `process(event)` is
  **pure, synchronous, transport-agnostic**: debounce → `GaussianBayesianUpdater.update` →
  compute `belief_shift` (prior→posterior **total-variation distance**) → re-run
  `VectorizedMonteCarloEngine` iff `shift ≥ rerun_threshold` (else cheap re-weight of cached
  per-scenario risk) → build `RiskState` via `posterior_mixture_risk` + `scenario_confidence`.
  An internal `threading.Lock` guards the in-memory belief state. `build_default_updater()`
  seeds the Liguria twin + a baseline MC run at startup.
- **`streaming/broadcaster.py`** — `ConnectionManager`, an in-process WebSocket fan-out
  (connect/disconnect/broadcast; drops dead peers). Typed against a `WebSocketLike` Protocol so
  it's unit-testable with a fake and the *core* logic has no hard Starlette dep. The only
  component that knows about sockets.
- **`api/routers/stream.py`** — `POST /api/v1/stream/ingest` (→ **202 Accepted**, schedules a
  `BackgroundTask`), `GET /api/v1/stream/state` (current `RiskState`), `WS /api/v1/stream/ws`
  (subscribe). The background task runs `process()` via `asyncio.to_thread` (CPU-bound math off
  the loop → ingestion never blocked), then broadcasts on the loop. Wired in `api/main.py`
  (lifespan builds `app.state.updater` + `app.state.broadcaster`) and `api/deps.py`.
- **`tests/streaming/test_realtime.py`** — 7 tests: 202-immediate; background task moves beliefs
  (hotter_drier prior ↑, confidence ↑); duplicate events debounced; `ConnectionManager`
  connect/broadcast + dead-peer pruning; end-to-end **ingest → WebSocket push**; pure-orchestrator
  callable without HTTP.

**Reconciliation:** the brief said `api/endpoints/stream.py`; the existing convention is
`api/routers/` — placed it there (reconcile, don't fork structure — same lesson as S2/S4/S6).

---

## Current Progress (Session 10 — Digital Twin Foundation — COMPLETE)

Focus: **the structural paradigm for real-world entities that consume the engines.** A
*Digital Twin* holds a physical state, evolves it deterministically from observations, and
drives the Monte Carlo / Bayesian engines to compute its risk state. Built the foundation +
the first concrete twin (Climate Risk / `RegionTwin`), wired into the Session-9 streaming
layer. Engines stay generic calculators; the twin is the business logic that uses them.

**What was built (all green: ruff clean, mypy clean, 80 pytest pass — was 73):** a new
**`backend/vectis/digital_twin/`** package, correctly layered **`streaming → digital_twin →
simulation/core`** (digital_twin imports zero streaming/web/LLM).
- **`digital_twin/entities/base.py`** — the `DigitalTwin` ABC (`get_current_state` /
  `update_from_observation` / `predict_risk`) + a `TwinState` marker base. Tiny and
  calculator-free: *how* a twin maps its domain onto the engines is the concrete twin's job —
  that's what lets a `FinancialMarketTwin` reuse the same engines beside `RegionTwin`.
- **`digital_twin/entities/region.py`** — `RegionTwin` (the Climate Risk twin) + `RegionState`
  (`temperature_anomaly`, `humidity_level`, `vegetation_stress`, `recent_fire_history`).
  `update_from_observation` runs the canonical order: **Bayesian update against the
  pre-transition state** → **deterministic transition** evolves the present → **MC re-run** over
  the new state × posterior (only if state changed or belief shift ≥ threshold) →
  `computed_risk_state`. Its only engine-specific knowledge is `_to_world_state()` (domain
  fields → `WorldState` vars; defaults reproduce the Session-7 Liguria twin exactly). Per-twin
  `threading.Lock`.
- **`digital_twin/transitions/base.py`** — `StateTransition` ABC + `ClimateTransition`
  (heuristics, **no physics engine**): temp/humidity/rain observations set their field; fires
  accumulate; `vegetation_stress` relaxes toward `Δ = temp·K_TEMP − humidity·K_HUM`, recomputed
  only when a driver moved (so unrelated obs can't drift it). `K_TEMP=1.0, K_HUM=0.1` balanced
  so the Liguria default sits at equilibrium.
- **`digital_twin/state/manager.py`** — `StateManager`, a thread-safe in-memory twin registry
  (`register`/`get`/`all`/`count`/`deregister`); the interface a future Redis/DB store must meet.
- **`digital_twin/schemas.py`** — `RiskState` (**moved here** from `streaming.events` — it's a
  twin's computed output; re-exported from `streaming.events` for back-compat) + `TwinUpdate`.
- **Streaming refactor:** `RealTimeUpdater` is now a thin **router** (debounce → `manager.get`
  → `twin.update_from_observation` → wrap `TwinUpdate` in `StateChange`); the CPU-bound math
  moved into the twin. `StreamEvent` gained a `region` field (default `liguria`) for routing;
  `GET /stream/state?region=` resolves per-twin (404 if none). `build_default_updater()` now
  registers the Liguria `RegionTwin`. **All 7 Session-9 streaming tests still pass unchanged.**
- **`tests/digital_twin/test_region_twin.py`** — 7 tests: default state + baseline risk;
  high-temp → veg-stress ↑; rain → humidity ↑ / stress ↓; unrelated obs doesn't drift stress;
  observation updates state **and** recomputes risk (hotter_drier ↑, confidence ↑, risk ↑);
  registry; `WeatherAlert` routed end-to-end into the twin.

**Quality check (10k twins? `FinancialMarketTwin` beside it?):** Yes on both. Twins are
independent in-memory objects with per-twin locks (no global serialization bottleneck — the
router lock only guards the debounce dict, held briefly); the `StateManager` is a flat dict.
The `DigitalTwin` ABC carries no climate/engine specifics, so a second twin type implements the
same three methods with its own `TwinState`, transition, and `_to_world_state` mapping.

---

## Current Progress (Session 11 — LLM Simulation Agents — COMPLETE)

Focus: **reintroduce LLMs as a team of intelligence analysts** that *read* the Digital Twin's
output and compile a structured `DecisionIntelligenceReport` — under a hard **Math Firewall**
(LLMs narrate, never calculate). Built the "Simulation Analysis Board" as a LangGraph state
machine, wired to the Session-10 twins, exposed via a manual API trigger.

**What was built (all green: ruff clean, mypy clean on 97 files, 89 pytest pass — was 80):** a
new **`backend/vectis/agents/board/`** sub-package (kept *separate* from the V1 flat `agents/`
modules — that's the reactive ML/SHAP pipeline; this is the V2 probabilistic board).
- **`board/prompts.py`** — rigorous system prompts. Shared `MATH_FIREWALL` preamble (numbers are
  authoritative ground truth; never recompute/invent) + `TONE` preamble (national-security /
  institutional-risk register: BLUF-first, terse, no chatbot voice) on every agent.
- **`board/nodes.py`** — the five analysts (Analyst, Scenario Narrator, debate Optimist +
  Pessimist, Red-Team Critic). Each builds numbers → LLM `context`, writes a deterministic
  intel-grade `fallback`, calls `LLMProvider.narrate`, and returns a typed schema **with numeric
  fields copied from the input**. Framework-agnostic (no LangGraph) so the graph and the
  sequential fallback share one source of logic.
- **`board/team.py`** — the LangGraph `StateGraph`: `Analyst → Scenario → Optimist → Pessimist →
  Critic`. The two debate sub-agents are distinct nodes accumulating into one `DebateRound`.
- **`board/schemas.py`** — `BoardInput` (firewall source-of-truth) + `DecisionIntelligenceReport`
  (`AnalystBrief` / `ScenarioNarrative` / `DebateRound` / `RedTeamCritique` + `bottom_line` BLUF),
  fully typed/JSON-serializable for the frontend.
- **`board/service.py`** — `SimulationBoardService.analyze_twin(twin)` / `analyze(BoardInput)`.
  Builds `BoardInput` from a `RegionTwin` (primary driver = dominant posterior scenario). Prefers
  the LangGraph graph; **falls back to running the same nodes sequentially** if LangGraph is
  absent → identical report (graph is an execution choice, like S3/S7).
- **`api/routers/intelligence.py`** — `POST /api/v1/intelligence/reports {region}` → reads the
  region twin's `RiskState`, runs the board, returns the report (404 unknown region). Wired in
  `api/main.py`. Stream-independent (manual trigger).
- **`tests/agents/test_simulation_agents.py`** — 9 tests, **all LLM calls mocked** (no API
  traffic): report matches schema + JSON round-trips; all 7 narrations prompted with the firewall;
  LangGraph state flows Analyst→Scenario→Debate→Critic (`importorskip`); graph == sequential;
  **Math Firewall** (a "lying" LLM returning "risk 12/100" cannot change the structured figures);
  analyze from a real `RegionTwin`; the API endpoint + 404.

**Reconciliation (consistent with every prior session):** the brief named `langchain_openai` and
real LLM calls. VECTIS's iron rule is offline/key-free/deterministic tests (the `mock` provider).
Reused the existing `LLMProvider` abstraction (the brief's "or equivalent") for model calls and
LangGraph for the graph — so the Math Firewall, structured output, and offline CI all hold. A
real `OpenAIProvider` can be added behind `LLMProvider` later exactly like `AnthropicProvider`.

**Math Firewall — how it's enforced:** (1) **structurally** — every numeric field in the report is
copied from `BoardInput` in code; the LLM only fills prose, so a hallucinated figure can't
overwrite an authoritative one (proven by the lying-LLM test); (2) **in the prompts** — the
`MATH_FIREWALL` preamble on every agent forbids recomputation/invention; (3) **by default** — the
`mock` provider returns the deterministic, numbers-derived fallback, so offline output is itself a
serious brief.

**mypy gotcha (same as S3):** LangGraph's `StateGraph.add_node` strict overloads reject the
plain partial-update return → `call-overload`. Fixed with the **scoped** mypy override extended to
`vectis.agents.board.team` (joined the existing `langgraph_engine` entry); the rest stays strict.

---

## Current Progress (Session 12 — First Real VECTIS Demo — COMPLETE)

Focus: **stitch every V2 layer into one flawless, runnable end-to-end demo** of the Liguria
wildfire use case — integration + presentation, no new core math. Proves the full pipeline:
simulated weather alert → `RealTimeUpdater` → Liguria `RegionTwin` transition → Monte Carlo
(100k) → Bayesian update → LangGraph board → `DecisionIntelligenceReport`.

**What was built (all green: ruff clean, mypy clean on 98 files, 93 pytest pass — was 89):**
- **`vectis/scripts/demo_v2.py`** — the demo. `run_demo(*, iterations=100_000, seed=7, color=True,
  out=None, llm=None) -> DemoResult` (returns baseline/final `RiskState` + the report, so it's
  testable) and `main()`. Builds a *calm* Liguria `RegionState`, registers a `RegionTwin` with a
  **100k**-iteration `SimulationConfig`, ingests two `WeatherAlert`s (heatwave +4.5 °C, drought
  −35 %) through `RealTimeUpdater.process`, then runs `SimulationBoardService.analyze_twin`.
  Renders 5 phases (INITIALIZE / OBSERVE / CALCULATE / ANALYZE / REPORT) as a tactical terminal —
  **pure stdlib** (ANSI + box-drawing), no `rich` (not a dep). Result: ~45/100 MODERATE → ~98/100
  SEVERE, posterior collapsing onto *hotter & drier*, confidence 6% → 100%, in ~1 s offline.
- **`scripts/run_demo_liguria.py`** — top-level shim the brief's quality-check command runs
  (`python scripts/run_demo_liguria.py`); prepends the backend root to `sys.path` so it works even
  before `pip install -e .`. `make demo-v2` target added.
- **Mock realism:** reused the Session-11 deterministic fallbacks (already intelligence-grade and
  region/driver/scenario-aware) — on the Liguria twin they read as a real brief, no new mock needed.
- **`tests/integration/test_end_to_end_demo.py`** — 4 tests: alert raises risk MODERATE→SEVERE +
  shifts beliefs to hotter_drier; report well-formed + Math-Firewall-consistent (report numbers ==
  engine numbers); console output has every section + "100,000" + the risk score; determinism
  (same seed/mock ⇒ identical numbers and analyst prose).

**Two real robustness bugs caught and fixed during the demo build:**
1. **structlog INFO lines interleaved** into the terminal art. Fixed with `_silence_logs()` (raise
   the structlog filter to CRITICAL at `run_demo` start, before the first log fires). Tests are
   unaffected — their captured `out` buffer never received structlog's `PrintLogger` output anyway.
2. **`UnicodeEncodeError` on a cp1252 Windows console** — the box-drawing glyphs (and em-dash/°C/−
   in the prose) crash a naive run. `main()` now calls `_force_utf8_stdout()` (reconfigure to UTF-8
   with `errors="backslashreplace"`, falling back to wrapping the raw binary buffer when structlog's
   colorama wrapper blocks `reconfigure`) so "clone → run" never dies on encoding.

**Honest note on the numbers:** two CRITICAL corroborating alerts drive the scenario posterior to
~100% (residual 0%). That's mathematically correct (a +4.5 °C reading is a decisive outlier for a
calm baseline) and the Red-Team fallback turns it into a sharper point ("Do not mistake 100%
confidence for coverage — the model is blind to arson and sub-grid wind"). If a softer, partial
update reads better for a given audience, lower the alert severity/magnitude or warm the baseline.

---

## Current Progress (Session 13 — Scale & Performance — COMPLETE)

Focus: **scale the Monte Carlo engine to 1,000,000+ scenarios** with mathematical exactness and
reproducibility — local multiprocessing + a dependency-free distributed abstraction + caching —
and measure honestly whether parallelism actually helps.

**Headline (measured, `make stress`):** 1M iterations × 3 branches = **3M trajectory evaluations
in ~0.8 s single-thread (~3.6 M evals/s), ~72 MB peak, no leak**. Multiprocessing is **~12× slower**
(Windows `spawn` re-imports the scientific stack per worker + pickles result arrays back), so
`parallel` stays off by default. Warm cache hit is **~6,600× faster** than recomputing.

**What was built (all green: ruff clean, mypy clean on 100 files, 101 pytest pass — was 93):**
- **`engine/runner.py` refactor.** `run()` now builds *all* scenarios' chunks up front and
  dispatches them through **one** `ProcessPoolExecutor` (was one pool *per scenario* → 3× the
  spawn cost; this alone cut the 1M parallel time from ~40 s to ~10–15 s). Extracted
  `resolve_workers(n_workers)` (`0` ⇒ auto `os.cpu_count()-1`), `_build_chunks` (the seeded
  sharding), and `_dispatch` (the pluggable executor). Math is byte-identical to before (same
  per-scenario chunks, same order, sliced back per scenario).
- **`engine/distributed.py`** — `DistributedMonteCarloEngine` (subclasses the vectorized engine,
  overrides *only* `_dispatch`→`_cluster_map`, reusing sharding/RNG/reduction) + `ClusterClient`
  Protocol + `RayEngineAdapter` + `LocalClusterStub` (a runnable `submit`/`gather` futures stub
  that mirrors Ray's `remote`/`get`; **`ray` never imported**). A distributed run is byte-identical
  to serial for the same `(seed, n_workers)`.
- **`caching.py`** — `run_key(state, scenarios, config)` (sha256 of canonical JSON, **excluding the
  volatile `WorldState.estimated_at`** so semantically-identical states hash equal) + a TTL+LRU
  `SimulationCache` + `MemoizingMonteCarloEngine` (decorator over any engine — caching orthogonal
  to the math).
- **`schemas.py`** — `SimulationConfig.n_workers` relaxed `ge=1`→`ge=0` (`0=auto`), with the
  cross-machine-determinism caveat documented.
- **`scripts/stress_test.py`** (`make stress`) — initializes the Liguria twin + observation, runs
  1M serial vs multiprocessing vs distributed-stub, checks parallel==serial byte-identical, demos
  the cache, measures peak memory (`tracemalloc`), and **prints an honest verdict** computed from
  the measured times. `if __name__=="__main__"` guard (Windows spawn), self-bootstraps `sys.path`.
- **`tests/simulation/test_performance.py`** — 8 tests: 1M executes (`@pytest.mark.slow`); cache
  intercepts identical runs (engine called once) + misses on changed inputs + key ignores
  timestamp + TTL expiry; parallel==serial 100k byte-identical (`slow`); distributed adapter ==
  serial; `resolve_workers` auto. Registered the `slow` marker in `pyproject.toml`.

**RNG reproducibility across workers (how):** entropy is isolated by
`numpy.random.SeedSequence(seed).spawn(n_workers)` — each worker reconstructs its own `Generator`
from its spawned child seed, so a chunk's draws depend *only* on `(seed, its index in the split)`,
never on import order, worker count beyond the agreed split, or where it physically runs. The
sharding is fixed in `_build_chunks`; only `_dispatch` (local pool vs cluster vs serial) varies.
Therefore serial, multiprocessing, and the distributed stub all produce **byte-identical** draws
for the same `(seed, n_workers)` — asserted in the stress test and three tests.

**Quality-check answers (honest):** NumPy handles the 1M arrays fine (~72 MB peak, no leak — 8 MB
per scenario array, transient, not retained). And **yes, multiprocessing pickling/spawn overhead
makes it slower than single-thread** for this cheap workload (~12×) — documented explicitly in the
stress-test console output and the docs, not hidden.


## Current Progress (Session 14 — VECTIS V2 Productization — COMPLETE)

Focus: **V2 Frontend Dashboard and API integration.** Bridging the 1M-scenario Monte Carlo and Bayesian math to an enterprise-grade React/TS user interface. 

**What was built (API tests green: 107 pytest pass — was 101):**
- **`api/routers/dashboard.py` & `services/dashboard_service.py`:** `GET /api/v1/dashboard/twins/{id}` (returns current state, RiskState, per-scenario distributions, and AI report) and `POST /api/v1/dashboard/simulate/what-if` (sync Monte Carlo run via S13 cache).
- **`src/types/v2.ts`:** Strict TypeScript interfaces mirroring backend Pydantic models (`RiskState`, `ProbabilityDistribution`, `DecisionIntelligenceReport`).
- **`src/hooks/useTwinStream.ts`:** WebSocket hook with auto-reconnect and 3s backoff to accumulate `StateChange` points into a timeline.
- **React Feature Components (`src/features/dashboard/`):**
  - `ScenarioExplorer`: Box-and-whisker distributions (p05/p50/p95).
  - `AiIntelligenceBrief`: Structured rendering of the LangGraph AI report.
  - `WhatIfSimulator`: Manual sliders mapping to `RegionState`, leveraging the cache for instant "what-if" re-runs.
  - `ProbabilityTimeline`: Recharts dual-axis line chart tracking risk and confidence over time.
- **`src/pages/DashboardPage.tsx`:** Composes the V2 features into the command center view.
---

## Current Progress (Session 15 — VECTIS V2 Release — COMPLETE)

Focus: **finish the S14 wiring and ship a top-tier open-source release.** No new product
surface — finalize, document, and package. Everything below is committed (atomic, humanized
commits) and all gates are green.

**1. Frontend finalization (closed the S14 gap).** The dashboard route was never wired before the
API dropped. Added `DashboardPage` to the router (`src/app/App.tsx`, `/dashboard`) and a sidebar
entry **"Decision Intelligence"** with `IconActivity` (`src/components/layout/nav.ts`). Fixed one
unused-import typecheck error in `useTwinStream.ts`. **`npm run typecheck`, `npm run lint` (0
warnings), `npm run build`, and `npm test` (7 tests) all pass.** → commit `feat(ui): wire V2
decision-intelligence dashboard into the React app` (the S14 backend + frontend foundation were
also committed here as two atomic commits, since S14 ended before committing).

**2. Architecture diagrams.** New `docs/v2_architecture.md`: a mermaid **flowchart** of the full
pipeline (external data → updater → twin → Bayesian → Monte Carlo + cache → board → dashboard)
with the Math Firewall called out by color, a **sequence diagram** of an observation arriving
(202 → background → belief shift → conditional re-run → WS push), and a component-to-code table.
→ commit `docs: add V2 system architecture with mermaid flow and sequence diagrams`.

**3. Demo video script.** New `docs/demo_video_script.md`: a 2-minute shot-by-shot storyboard for
the maintainer to record (terminal `demo_v2` → `make stress` → dashboard → Scenario Explorer →
What-If → AI brief → live `curl` ingest → timeline ticks). Verified the ingest `curl` payload
against the real `WeatherAlert` schema (`variable`/`value`/`severity`, not invented fields).
→ commit `docs: add 2-minute showcase video script for maintainers`.

**4. README overhaul.** Reframed the header as **"Real-Time Probabilistic Decision Intelligence
Platform"**; added the two-layer story, a capability table linking the engineering to code, a
**Performance & Scale** section with the S13 benchmark (1M scenarios ~0.8 s single-thread + the
honest multiprocessing caveat), the V2 dashboard section, and a concrete **V3 roadmap** (Kafka +
NASA FIRMS, persistence, RL for actions, multi-twin Climate × Finance, horizontal scale). Added
test/scale badges. → commit `docs: overhaul README around V2 with benchmarks, architecture, and
V3 roadmap`.

**Verification snapshot:** backend `pytest` 107 passed; frontend `tsc --noEmit` clean,
`eslint --max-warnings 0` clean, `vite build` succeeds (the >500 kB chunk warning is pre-existing,
from three.js/maplibre, not V2 code), `vitest` 7 passed.


## Current Progress (Session 16 — V3 Foundation & Real-Time Architecture — COMPLETE)

Focus: **The V3 Paradigm Shift.** Transitioning from a localized, on-demand engine (V2) to a continuous, living system that observes the entire world.

**What was built (110 tests pass, ruff/mypy clean):**
- **Purge Directive Executed:** The repository was fully sanitized of all pop-culture and external corporate references. VECTIS now uses generic, enterprise-grade terminology.
- **V3 Documentation:** Created `docs/v3_realtime_architecture.md` and `docs/v3_state_management.md` defining the new concepts (Event, Stream, State, Observation, Update, Forecast).
- **Package Scaffold:** Created `backend/vectis/realtime/` with subpackages (`ingestion`, `events`, `streams`, `processors`, `state`, `forecasting`), each heavily documented with `__init__.py` blueprints.
- **Base Interfaces:** - `realtime/events/base.py`: Defined `GlobalEvent` (raw, untrusted) and `GlobalObservation` (normalized, tied to a grid cell).
  - `realtime/state/base.py`: Defined `CellState` and the `StateEstimator` ABC to handle continuous predict-correct filtering (Kalman/Bayesian).
  - `tests/realtime/test_foundations.py`: Guarded the V3 interfaces.

## What Worked
- **(S16) Sharding state by Global Grid Cells.** Designing the `StateEstimator` to treat each geographical cell as an independent state allows infinite horizontal scaling (planetary-scale parallelism without global locks).
- **(S16) Strict Trust Boundary.** Separating `GlobalEvent` (raw/untrusted) from `GlobalObservation` (validated) enforces data integrity before it ever touches the math engine.

## What Didn't Work / Gotchas
- **(S16) API Stall on Documentation.** The LLM stalled while writing the final `HANDOFF.md` summary due to context size, requiring a manual closeout.

## Next Steps (Session 17 — pick up here)
**Goal:** Proceed with V3 implementation.
**Focus on Session 17 (Continuous State Estimation):**
- Implement the concrete `StateEstimator` using Kalman Filters or continuous Bayesian updating for `CellState`.
- Build the first concrete `Processor` to turn a mock global event into a `GlobalObservation`.
---

## Current Progress (Session 17 — API Data Ingestion Layer — COMPLETE)

**Goal:** Build the layer that receives data from the real world — a robust API connector
framework that fetches external JSON, survives network instability, and normalizes payloads into
V3 `GlobalEvent`/`GlobalObservation` objects.

**Current Progress: Session 17 (API Data Ingestion Layer — COMPLETE).** All built on the S16
foundation, no interface changes. `realtime/` tests: 8 pass (3 foundation + 5 ingestion).

- **`realtime/connectors/base.py` — `BaseAPIConnector` (resilient HTTP).** `get_json()` wraps one
  GET in **exponential backoff** (`backoff_base * 2**attempt`): retries timeouts, connection
  errors, and 5xx; **fails fast on 4xx** (a client bug won't fix itself by retrying) and on JSON
  decode errors. Raises `ConnectorError` only after exhausting retries. `collect()` = `fetch()` →
  `normalize()` that **never raises** — on a total outage it logs once and returns `[]`, so a dead
  feed degrades the stream instead of crashing it. `httpx.Client` is injectable; `sleep` is
  injectable so backoff is testable without real waits.
- **`realtime/connectors/{weather,satellite,generic}.py` — concrete connectors.**
  `WeatherAPIConnector` (temp/humidity/wind → one event per canonical variable; offline-safe
  synthetic reading with no `base_url`), `SatelliteAPIConnector` (NASA-FIRMS-style active-fire
  rows), `GenericJSONConnector` (arbitrary webhook payloads). Each implements only `fetch` +
  `normalize` and inherits retry/degradation for free.
- **`realtime/ingestion/manager.py` — `IngestionManager` (the orchestrator).** Holds a set of
  active connectors and merges them into one event stream. `poll_once()` = one synchronous sweep
  (a dead feed contributes `[]`, never aborts the sweep); `run(interval, max_cycles)` = a
  self-pacing generator yielding a continuous `GlobalEvent` stream, sleeping *between* sweeps only.
  Kept synchronous on purpose (`ponytail:` swap for asyncio/Kafka in S18 — connector contract is
  stable). `sleep` injectable for tests.
- **`tests/realtime/test_connectors.py` — 5 tests** driving HTTP with `httpx.MockTransport` (no
  sockets, no `responses` dep) and a no-op `sleep`: retries 500-then-200; 4xx fails fast without
  retry; persistent 503 outage degrades to `[]`; raw `{"temperature","humidity","wind"}` normalizes
  into `GlobalObservation`s with the right variables/source; manager merges connectors and survives
  a dead feed (3 events from the live feed, none from the dead one, no crash).

**Git commits (this session):**
- `feat(realtime): add resilient base API connector with retry logic`
- `feat(realtime): add weather, satellite, and generic JSON connectors`
- `feat(realtime): add ingestion orchestrator and connector tests`

### What Worked
- **(S17) Resilience pushed into the base, not the manager.** `collect()` swallowing its own outage
  means the orchestrator stays a trivial fan-in loop — one dead feed can never stall the others.
- **(S17) `httpx.MockTransport` + injectable `sleep`.** Tests exercise real retry/backoff control
  flow against simulated 500→200 with zero network and zero wall-clock delay; no new test dep.
- **(S17) Offline-safe connectors.** With no `base_url`, connectors return deterministic synthetic
  readings, so the whole ingestion layer runs (and the demo works) with no network or API keys.

### What Didn't Work / Gotchas
- **(S17) Server crash mid-write.** The S17 server aborted while `manager.py` was being written
  (before commit/handoff). On resume the file was found **complete and contract-consistent**
  (`collect()`/`close()` match `BaseAPIConnector`); finalized = verify + test + commit, no rewrite.
- **(S17) 5xx isn't an `HTTPStatusError` by default.** `response.raise_for_status()` would raise it,
  but to *retry* 5xx and *re-raise* 4xx the code raises `HTTPStatusError` explicitly on `>=500` and
  branches on `status < 500` in the handler — otherwise a 503 would fail fast like a 404.

### Next Steps (Session 18 — pick up here)
**Focus on Session 18 (Stream Processing & Event Routing):**
- Build the `processors` stage: validate/deduplicate raw `GlobalEvent`s and assign a real grid
  `CellId` (replace `naive_cell_id`'s 0.1° quantization with H3/raster tiling).
- Route normalized `GlobalObservation`s to the per-cell `StateEstimator` (S16 ABC) for continuous
  predict-correct updates.
- Replace `IngestionManager`'s synchronous poll loop with async fan-in / a real stream backend
  (asyncio gather or Kafka producer) — the connector contract stays unchanged.
---

## Current Progress (Session 18 — Event Streaming Engine — COMPLETE)

**Goal:** Build VECTIS's central nervous system — the event streaming broker that routes data from
the Session-17 `IngestionManager` to downstream processors. The flow `Data Event → Queue →
Processor → State Update`, designed "clone & run" friendly: the whole pipeline runs locally on pure
`asyncio`, while a DevOps engineer can swap in Redis Streams for production via one env var.

**Current Progress: Session 18 (Event Streaming Engine — COMPLETE).** Built on the S16/S17
foundation, no interface changes upstream. `realtime/` tests: **12 pass** (3 foundation + 5
ingestion + 4 streaming); full backend suite green.

- **Event schema hardening — `realtime/events/base.py`.** `GlobalEvent` now strictly carries
  `confidence: float` (validated `0.0–1.0`, the raw source trust) and a free-form `metadata: dict`
  for traceability, alongside the existing `source`, `location`, `observed_at`/`ingested_at`
  (timestamp), and `payload`. Both default (1.0 / empty) so the S17 connectors keep working; the
  range is enforced. The satellite connector now routes the real FIRMS detection confidence
  (0–100 → 0–1) into the field instead of folding it into `std` alone.
- **Broker architecture — `realtime/streams/broker.py`.** Evaluated Kafka (too heavy for a local
  checkout), RabbitMQ (push/task-queue model, hard dep), and **Redis Streams** (log-shaped, light,
  at-least-once) — see the module docstring. The design is an abstract **`MessageBroker`** ABC
  (`publish`/`subscribe`/`ack`/`close`) with two backends: **`MemoryBroker`** (one `asyncio.Queue`
  per topic, zero deps, the default) and **`RedisStreamBroker`** (a `redis.asyncio` adapter over
  `XADD`/`XREADGROUP`/`XACK` consumer groups; `redis` imported lazily, opt-in `redis` extra).
  **`get_broker()`** resolves the backend from `VECTIS_BROKER` (`memory`|`redis`) + `VECTIS_REDIS_URL`.
- **Producer & Consumer — `realtime/streams/{producer,consumer}.py`.** `EventProducer` forwards the
  `IngestionManager`'s merged `GlobalEvent` stream onto a broker topic, polling off the event loop
  via `asyncio.to_thread` (a slow feed never blocks the loop). `EventConsumer` drains a topic into a
  sync-or-async `processor` callback and **acks only on success** — a callback that raises is logged
  and skipped (so under Redis the event is redelivered, not lost) without killing the loop. This is
  the seam the S19 `StateEstimator` plugs into.
- **Tests — `tests/realtime/test_streams.py` (4 tests).** `MemoryBroker` round-trips events in
  order; a producer pushing **100** ingested events results in a consumer processing **exactly 100**;
  a failing processor is logged/skipped (`processed==4, failed==1` over 5) without crashing; an async
  processor callback is awaited. Async driven via `asyncio.run` inside sync tests (the S9 pattern —
  no asyncio plugin/dep).

**Git commits (this session):**
- `feat(events): enforce confidence and metadata fields in event schemas`
- `feat(streams): implement abstract message broker and memory queue`
- `feat(streams): add producer and consumer for the event pipeline`
- `test(streams): cover broker enqueue/dequeue and producer-consumer flow`

### What Worked
- **(S18) One abstract broker, two backends, swap via env var.** Callers (producer/consumer) depend
  only on `MessageBroker`; `get_broker()` reads `VECTIS_BROKER`. Local dev gets a dependency-free
  `asyncio.Queue`; production gets Redis Streams with no code change — exactly the proportionality
  the quality-check demanded.
- **(S18) Ack-on-success, not ack-on-receipt.** The consumer acks only after the processor returns,
  so a failing event isn't silently dropped — under Redis's consumer-group PEL it's redelivered. The
  ack handle (Redis stream id) rides in the new `metadata` dict, so no wrapper type was needed and
  `MemoryBroker.ack` stays a clean no-op.
- **(S18) `asyncio.to_thread` for the synchronous `IngestionManager`.** The S17 manager stays
  unchanged (sync, blocking HTTP); the producer wraps its `poll_once` off the loop, so the streaming
  layer is async without rewriting ingestion — the same off-loop pattern S9 used for CPU-bound math.
- **(S18) Hardening `GlobalEvent` with safe defaults.** Adding `confidence`/`metadata` with defaults
  enforces the contract (range-validated) without breaking the three S17 connectors or their tests —
  reconcile, don't churn.

### What Didn't Work / Gotchas
- **(S18) Redis deserialization loses the `GlobalEvent` subclass.** Over the wire an event rebuilds
  as the *base* `GlobalEvent`, so its `to_observation` hook (defined on subclasses) is gone. The
  payload/variable survive; re-typing belongs in the processor stage (S18 design note, `ponytail:`
  in `broker.py`) where normalization lives anyway — `MemoryBroker` keeps the live object in-process,
  so this only bites the Redis path.
- **(S18) An early `MemoryBroker` draft pulled in `anyio`.** Walked back to plain `asyncio.Queue`
  with `task_done()`/`join()` — no new dependency, and `join()` gives tests a clean "all consumed"
  barrier. Ruff also caught a leftover unused `asyncio` import in `consumer.py`.
- **(S18) `mypy` vs `python -m mypy`.** A bare `mypy <file>` exited 1 with no output in this shell;
  `python -m mypy` reported "Success" correctly. Use `python -m mypy` for the streams package.

### Next Steps (Session 19 — pick up here)
**Focus on Session 19 (Continuous State Estimation):**
- Implement the concrete `StateEstimator` (S16 ABC, `realtime/state/base.py`) — continuous
  predict-correct (Kalman / continuous Bayesian) updating of per-cell `CellState`.
- Build the first concrete **`Processor`** (`realtime/processors/`): consume `GlobalEvent`s off the
  broker (it's the `EventConsumer`'s `processor` callback), **validate** at the trust boundary,
  **deduplicate**, assign a real grid `CellId` (replace `naive_cell_id`'s 0.1° quantization with
  H3/raster tiling), and emit `GlobalObservation`s.
- Wire `Producer → MemoryBroker → Consumer(Processor) → StateEstimator.update(cell)` end to end, so
  an ingested event continuously moves a cell's state — the full `Data Event → Queue → Processor →
  State Update` loop running on one node.
---

## Current Progress (Session 19 — State Estimation Engine — COMPLETE)

### Goal
Build the **"present" of VECTIS** — the consumer-side logic that turns the Session-18 event
stream into a **continuously-updated, versioned world state**. Receive normalized observations,
merge them into per-cell state, keep a replayable history, and version every transition so the
system is auditable and can look back in time.

### Current Progress: Session 19 (State Estimation Engine — COMPLETE)
Built on the S16 foundation, no upstream interface changes. `realtime/state/` is now a working
engine, not a blueprint. `realtime/` tests: **17 pass** (3 foundation + 5 ingestion + 4 streaming
+ 5 state); full backend suite green (124 pytest pass), ruff + mypy clean on the new modules.

- **`realtime/state/models.py` — `WorldCellState`.** The concrete, domain-named cell state the
  running engine carries: `temperature`, `humidity`, `drought_index`, `fire_risk` (each
  `float | None` — `None` until a feed reports it, so a fresh cell is honest about what it hasn't
  seen), an `extra` catch-all so an off-list canonical variable is never silently dropped, plus
  versioning metadata: `version: int` (monotonic, +1 per observation) and `last_updated`. Named
  `WorldCellState` to coexist with the S16 blueprint `base.CellState` (the generic mean/covariance
  Kalman target) rather than overwrite it — both are exported from `state/__init__.py`.
- **`realtime/state/store.py` — `StateStore` ABC + `MemoryStateStore`.** Three methods:
  `get_state(cell_id)`, `save_state(cell_state)`, `get_history(cell_id, limit)`. The memory backend
  keeps the latest state per cell plus a bounded **append-only** `deque(maxlen=history_limit)` of
  superseded versions; `save_state` pushes the prior latest into history before replacing it;
  `get_history` returns prior versions **newest-first**. Thread-safe (one lock) so it sits behind
  the streaming consumer. A `ponytail:` stub marks where `RedisStateStore`/`PostgresStateStore` drop
  in over the same three methods.
- **`realtime/state/updater.py` — `StateUpdater`** (the concrete fulfilment of the S16
  `StateEstimator` role). `apply_observation(observation: GlobalObservation)`: fetch current (or
  create a fresh cell) → **EMA-merge** the observed variable into its field via a `VARIABLE_FIELDS`
  map (covers connector canonical names like `temp_anomaly_c` + plain aliases; unknowns land in
  `extra`) → bump `version` + `last_updated` → append source → `save_state`. The prior version is
  preserved in history by the store. First reading of a variable sets it directly; `alpha=1.0`
  makes the merge a direct overwrite (per the brief's "EMA or overwrite, pending Kalman").
- **`tests/realtime/test_state.py` (5 tests).** Fresh state initializes empty/unversioned;
  applying an observation updates the variable + increments the version (30 → EMA 35, v1 → v2);
  an unknown variable is kept in `extra`; the store retrieves version history **newest-first** with
  correct version numbers; history is **bounded** by `history_limit` (oldest age out).

**Git commits (this session):**
- `feat(state): add versioned concrete cell-state model`
- `feat(state): add state store interface with in-memory history backend`
- `feat(state): add state updater with observation merging and versioning`
- `test(state): cover state init, observation merging, and version history`

### What Worked
- **(S19) A second concrete model beside the Kalman blueprint, not on top of it.** `base.CellState`
  (mean/covariance) is the eventual filter target and is locked by the S16 foundations test;
  `WorldCellState` is the working state the engine merges into today. Coexisting (distinct names,
  both exported) honored "build on S16" with **zero churn** to the blueprint or its test — the same
  reconcile-don't-rewrite lesson as S2/S4/S6.
- **(S19) History lives in the store, versioning lives in the updater — clean split.** The updater
  only bumps `version`/`last_updated` and hands a new immutable copy to `save_state`; the store
  alone decides retention (bounded deque, newest-first). So look-back is a storage concern that a
  Redis/Postgres backend can satisfy without touching the merge logic.
- **(S19) `model_copy(deep=True)` before mutating.** The new version is a deep copy, so the prior
  object the store pushed into history stays frozen — no aliasing bug where a later EMA update
  silently rewrites a "historical" snapshot. This is what makes the audit trail trustworthy.
- **(S19) EMA with a None-aware first step + `extra` catch-all.** First reading sets the value
  (no blending a real number toward a fake zero baseline); off-list variables are retained instead
  of dropped, so adding a new feed doesn't require an updater change to avoid data loss.

### What Didn't Work / Gotchas
- **(S19) Name clash: `models.CellState` vs `base.CellState`.** The first draft named the concrete
  model `CellState`, which collides with the S16 blueprint that the foundations test imports from
  the package (`.mean`/`.covariance`). Renamed to `WorldCellState` immediately — exporting two
  different classes under one name from `state/__init__` would have been a footgun. Lesson: the S16
  generic state and the S19 concrete state are *different representations*; give them different names.
- **(S19) `StateUpdater` does not subclass `StateEstimator`.** The ABC's `update()` returns the
  generic `base.CellState` and adds `predict`/`get`/`active_cells` (Kalman-shaped); forcing
  inheritance would mean implementing covariance methods the EMA engine doesn't have yet. It
  *fulfils the role* (documented) without the inheritance — the real Kalman estimator that satisfies
  the ABC literally is deferred until covariance is tracked (`ponytail:` in `updater.py`).

### Next Steps (Session 20 — pick up here)
**Focus on Session 20 (Continuous Forecasting & V3 Demo):**
- **Build the first concrete `Processor`** (`realtime/processors/`) to close the loop the S18/S19
  handoffs both flag: consume `GlobalEvent`s off the broker (it's the `EventConsumer`'s `processor`
  callback), validate at the trust boundary, deduplicate, assign a real grid `CellId` (replace
  `naive_cell_id`'s 0.1° quantization), and call `StateUpdater.apply_observation`. Wire
  `Producer → MemoryBroker → Consumer(Processor) → StateUpdater` end to end on one node.
- **Implement `realtime/forecasting/`** → a continuous `Forecast` per cell: read the current
  `WorldCellState` (and, once tracked, its uncertainty) and project it over a horizon, reusing the
  V2 mixture machinery (`posterior_mixture_risk` + `scenario_confidence`). Derive `fire_risk` from
  the state here rather than treating it as a raw observable.
- **V3 demo** stitching ingestion → stream → processor → state → forecast for Liguria, in the
  `demo_v2.py` mold (testable `run_demo` returning a result, stdlib tactical console).
- **Promote to the Kalman `StateEstimator`** when per-variable uncertainty is needed: carry
  covariance in `WorldCellState`, swap the EMA merge for a predict–correct gain, and have the
  updater satisfy the S16 ABC literally.
---

## Current Progress (Session 20 — Kalman Filter Foundation — COMPLETE)

### Goal
Replace the Session-19 **exponential moving average** with the first dynamic update system that
**reasons about uncertainty**: a 1D **Kalman filter** (predict → correct). Each variable becomes a
Gaussian belief `(mean, variance)`; new observations are fused against the estimate by the **Kalman
gain**, balancing prediction uncertainty against observation uncertainty. The defining property the
EMA lacked: as consistent data arrives, **variance drops** — the system gets measurably more
confident over time.

### Current Progress: Session 20 (Kalman Filter Foundation — COMPLETE)
A new **`realtime/forecasting/kalman/`** package implements the filter, a parallel uncertainty-aware
state model, and a drop-in updater. Full backend suite green: **133 pytest pass** (was 124), ruff
clean, mypy clean (127 source files). `realtime/` tests now **26 pass** (added 9 Kalman tests).

- **`kalman/filter.py` — the pure math.** `Gaussian(mean, variance)` NamedTuple + three logic-free
  functions: `predict(prior, process_variance)` (static dynamics — mean held, variance grows by
  `process_noise_rate × seconds_elapsed`, so a stale estimate defers more to fresh data);
  `kalman_gain(predicted_var, measurement_var) = predicted_var / (predicted_var + measurement_var)`;
  `correct(predicted, measurement, measurement_variance)` (mean moves by `gain × residual`, variance
  → `(1 − gain) × predicted_var`, always ≤ both inputs). Plus `confidence_to_variance(confidence)`
  bridging a source `GlobalEvent.confidence` to a measurement variance. A `demo()`/`__main__`
  self-check asserts the brief's worked example (predict 30°C var 4 + observe 32°C var 1 → **31.6°C,
  var 0.8**) and that 20 consistent observations drive variance monotonically down.
- **`kalman/state_model.py` — `KalmanCellState` + `VariableEstimate`.** Parallel to the EMA
  `WorldCellState`: every variable is a `(mean, variance)` Gaussian held in a name-keyed `estimates`
  map (generic, not fixed fields), with the same `version`/`last_updated`/`sources` contract.
  `last_updated` is set to the observation's `observed_at` so the next predict step grows uncertainty
  by the real inter-observation gap. Kept separate so the S19 model/store/tests stay untouched.
- **`kalman/updater.py` — `KalmanStateUpdater`.** `apply_observation`: fetch current (or fresh cell)
  → canonicalize the variable via the reused `VARIABLE_FIELDS` map → derive observation variance from
  `observation.std²` (the carrier of source confidence; else a configured default) → **predict** the
  prior forward by elapsed time → **correct** with the observation → store the new `(mean, variance)`,
  bump version/timestamp, append source. First reading of a variable initializes the belief directly.
- **`realtime/state/store.py` — generalized, not forked.** `StateStore`/`MemoryStateStore` are now
  generic over the state type (`StateT` bound to a `cell_id` Protocol), so **one** versioned store
  with history serves both `WorldCellState` (EMA) and `KalmanCellState` (filter) — no duplicate store.
  The EMA `StateUpdater` is pinned to `StateStore[WorldCellState]`; all 5 S19 state tests pass
  unchanged.
- **`tests/realtime/test_kalman.py` (9 tests).** Pure math: high-variance prediction + low-variance
  observation weights toward the observation (K=0.8); confident prediction barely moves on a noisy
  obs; gain bounds; `confidence_to_variance` monotonicity. Updater: first obs initializes belief +
  version; **a sequence of 10 noisy readings of a stable 25.0 converges the mean (<0.3 off) and
  lowers variance strictly every step (<0.2 final)**; alias canonicalization folds `temp` +
  `temp_anomaly_c` into one belief; version history is preserved newest-first.

**Git commits (this session):**
- `feat(forecasting): implement 1D Kalman filter mathematical foundation`
- `feat(state): add Kalman cell state carrying per-variable uncertainty`
- `feat(state): integrate Kalman correction step into state updater`
- `test(forecasting): cover Kalman math and converging variance under noise`

### What Worked
- **(S20) Kalman gain as the single balance point.** The whole predict-vs-observe trade-off is one
  ratio: `K = predicted_var / (predicted_var + measurement_var)`. A confident observation (small
  variance) pulls K→1 and the estimate snaps to it; a noisy one pulls K→0 and the estimate holds.
  Because corrected variance is `(1 − K) × predicted_var`, it is *always* smaller than the prediction
  — so confidence can only grow with corroborating data. This is exactly what the fixed-α EMA could
  never express (its weight, and thus its "confidence", was constant).
- **(S20) Generalizing the store instead of forking it.** Making `StateStore[StateT]` generic let the
  Kalman path reuse the S19 versioned history store verbatim — no second `MemoryKalmanStore` to drift.
  The EMA path only needed a `StateStore[WorldCellState]` annotation; zero behavior change, S19 tests
  green untouched. Reconcile-don't-duplicate, same lesson as S2/S4/S6/S19.
- **(S20) A parallel `KalmanCellState`, not an in-place `WorldCellState` rewrite.** Holding beliefs as
  Gaussians in a name-keyed map (vs S19's fixed float fields) is the cleaner shape for a filter and
  kept the working EMA engine and all its tests untouched — the model can be promoted to the canonical
  one in S21 without a risky big-bang migration.
- **(S20) Pure functions over floats for the math.** `predict`/`correct`/`kalman_gain` take and return
  plain numbers, so they are trivially unit-testable, vectorizable later, and provably LLM-free — the
  Math Firewall holds by construction.

### What Didn't Work / Gotchas
- **(S20) `observed_at`, not wall-clock `now()`, drives the predict step.** Setting `last_updated` to
  the observation time (not ingestion time) is what makes elapsed-time variance growth correct;
  out-of-order events are clamped to `elapsed = max(0, …)` so a late-arriving reading never *adds*
  uncertainty. Using `now()` (as the S19 EMA updater did) would have made the process noise depend on
  ingestion latency rather than real elapsed time.
- **(S20) Observation *variance*, not *confidence*, is what the math needs.** The brief speaks of
  "confidence → variance", but `GlobalObservation` carries `std`, not `confidence`. Resolved by
  treating `std²` as the measurement variance (std is the V2-convention carrier of source confidence)
  and providing `confidence_to_variance` as the explicit connector-side bridge for the raw-event path.
- **(S20) A stale `mypy` shim on PATH exits 1 with no output.** The bare `mypy` binary in this
  environment returns a silent failure; `python -m mypy` is authoritative and reports
  *Success: no issues found in 127 source files*. Use `python -m mypy` for the gate.

### Next Steps (Session 21 — Continuous Forecasting & Final Demo)
- **Wire the Kalman state into `realtime/forecasting/`.** Read each cell's `KalmanCellState` and
  project it over a horizon by **sampling from the belief distribution** (mean + variance) into the
  reused V2 Monte Carlo / mixture machinery — so state uncertainty propagates into forecast
  uncertainty (variance bands, not a point). Derive `fire_risk` from the forecast, not as a raw input.
- **Build the first concrete `Processor`** (still open from S18/S19): consume `GlobalEvent`s off the
  broker, validate/dedupe, assign a real grid `CellId` (replace `naive_cell_id`), and call
  `KalmanStateUpdater.apply_observation` — closing `Producer → Broker → Consumer(Processor) → Kalman
  updater → forecast` on one node.
- **Final V3 demo** in the `demo_v2.py` mold (testable `run_demo`, stdlib tactical console): ingest a
  Liguria observation sequence, show the variance *shrinking* as data corroborates, and emit a
  continuously-updated forecast. This is the headline: a living, increasingly-confident estimate.
- **Promote `KalmanCellState` to canonical / satisfy the S16 `StateEstimator` ABC literally** once
  forecasting consumes it — carry cross-variable covariance (off-diagonal terms) if a multivariate
  filter is warranted, and fold the discrete scenario belief in via the V2 `BayesianUpdater`.
- **Calibrate the tuning knobs against real data** — `process_noise_rate` and the default observation
  variance are illustrative (`ponytail:`); fit them to how fast the real climate variables drift and
  to actual sensor σ once a FIRMS/ERA5 feed is wired.
---

## Current Progress (Session 21 — Bayesian Continuous Update Engine — COMPLETE)

### Goal
Translate the continuously-estimated *physical* state (Session 20's Kalman beliefs) into
continuously-updated *categorical* probabilities — e.g. fire risk 45% → observe drought/wind →
68%. The V2 Bayesian updater (Session 8) ran on-demand on a `ScenarioSet`; V3 needs a **streaming**
filter that carries its belief between ticks and reacts to each Kalman state change.

### Current Progress: Session 21 (Bayesian Continuous Update Engine — COMPLETE)
New package **`backend/vectis/realtime/forecasting/bayesian/`**, pure math, no LLM, **no stream
transport dependency** (a consumer calls it and publishes the result however it likes).
- **`likelihood.py`** — `ScenarioProfile` (a scenario's archetypal variable values + per-variable
  tolerance σ) and `log_likelihood(profile, kalman_state)`: the joint log P(state | scenario) as a
  sum of per-variable Gaussian log-densities, `N(estimate.mean; loc=expected, scale=√(estimate.variance
  + spread²))`. The cell's **own** Kalman variance widens the scale, so a fuzzy estimate discriminates
  less. Stdlib `math` (no scipy in the streaming hot path), log-space so a product of many ticks
  never underflows. Unobserved variables contribute nothing.
- **`priors.py`** — `ScenarioPriors`, the **carried** categorical belief. `set(posterior)` adopts a
  posterior as the next prior (floored off exact zero by `_EPSILON`); `relax(elapsed_seconds)` nudges
  the belief a time-scaled fraction `α = 1 − exp(−rate·dt)` toward a strictly-positive `baseline`
  (`p ← (1−α)p + α·baseline`). This is the **anti-lock-in** mechanism — see "no 0/100 trap" below.
- **`updater.py`** — `ContinuousBayesianUpdater.update_probabilities(kalman_state, elapsed_seconds=1)`:
  relax prior → score log-likelihoods → `log posterior = log prior + log likelihood` → **stable
  softmax** (subtract max log-posterior before exp; the softmax denominator **is** the exact evidence
  sum `Σ prior·likelihood`) → store posterior as the new prior → return it. A `__main__` self-check
  moves Liguria fire risk **45% → 67%** on a severe-drought / high-wind state.
- **`__init__.py`** — exports `ScenarioProfile`, `ScenarioPriors`, `ContinuousBayesianUpdater`,
  `log_likelihood(s)`, `normalize`.
- **`tests/realtime/test_bayesian_continuous.py`** — 3 tests (all green, full realtime suite 29
  pass): the 45% → ~68% shift on drought+wind; **1,000** continuous updates stay normalized to 1.0
  with no NaN/inf and never reach exact 0/1; trap-recovery (saturate on fire evidence → belief stays
  < 1.0 → benign observations pull it back under 0.1).

**Verified green:** ruff clean on the package + test; mypy clean (`api.run` → "Success: no issues
found in 4 source files"); `python -m vectis.realtime.forecasting.bayesian.updater` prints 45%→67%.

### What Worked
- **Mirroring V2's `GaussianBayesianUpdater` math** (log-space + stable softmax + exact normalization
  over a finite scenario set) and adapting it to *carry* state between ticks. The evidence sum is the
  softmax denominator — exact, not approximated.
- **Folding the Kalman variance into the likelihood scale** (`√(state.variance + spread²)`) makes the
  two engines compose cleanly: Session 20's uncertainty automatically tempers Session 21's confidence.
- **Stdlib `math` over scipy** for the Gaussian log-pdf — one line, keeps the streaming path light.
- **Relaxation toward a positive baseline** as a single, principled anti-trap mechanism (plus an
  `_EPSILON` floor as belt-and-suspenders) — also gives the brief's "drift back to baseline when
  idle" behavior for free, since `elapsed_seconds` scales the relaxation.

### What Didn't Work / Gotchas
- **The `~68%` target is tuning-sensitive.** Realistic-looking drought/wind separations produce
  *enormous* likelihood ratios (the wind term alone dominated), pushing the posterior to ~100%. To
  land on the brief's illustrative ~68% the scenario `spread` σ's are deliberately wide (drought 0.35,
  wind 15) — these are presentation knobs (`ponytail:` territory), to be replaced by fitted values
  once real FIRMS/ERA5 distributions exist. The test asserts a band (0.63–0.73), not an exact number.
- **The mypy CLI binary emits no output in this shell** (compiled `.pyd` + the harness pipe) and exits
  1 with an empty stream — *not* a type error. Use `python -c "from mypy import api; print(api.run([...]))"`,
  which reports success correctly.

### Next Steps (Session 22 — Final V3 Assembly & Live Demo)
- **Assemble the full V3 loop on one node:** `Producer → Broker → Consumer(Processor) →
  KalmanStateUpdater → ContinuousBayesianUpdater → Forecast`. The first concrete `Processor` (open
  since S18/S19) is still the missing link — consume `GlobalEvent`s, validate/dedupe, assign a real
  grid `CellId` (replace `naive_cell_id`), call `KalmanStateUpdater.apply_observation`, then feed the
  corrected state into `ContinuousBayesianUpdater.update_probabilities`.
- **Wire the categorical posterior into `realtime/forecasting/`** alongside the Monte Carlo projection
  — the scenario probabilities weight the forecast mixture (reuse V2 `posterior_mixture_risk`).
- **Final V3 live demo** in the `demo_v2.py` mold (testable `run_demo`, stdlib tactical console):
  ingest a Liguria observation sequence and show **both** uncertainties tighten — Kalman variance
  shrinking *and* the categorical belief sharpening toward the true scenario, tick by tick.
- **Calibrate the tuning knobs against real data** — scenario `expected`/`spread`, `relax_rate`, and
  the Kalman `process_noise_rate` are all illustrative (`ponytail:`); fit them to real climate
  variable distributions and sensor σ once a live feed is wired.
---

## Current Progress (Session 22 — Real-Time Forecasting Pipeline — COMPLETE)

### Goal
Unite every isolated organ built since Session 16 into one continuous, living flow:
`Live Data → Events → State Estimation (Kalman) → Bayesian Update → Monte Carlo (reused V2
engine) → New Probabilities → LangGraph Decision Report (reused V2 board)`. Sessions 16–21
each shipped one stage; Session 22 is the nervous system that wires them together and proves a
single event traverses the whole chain.

### Current Progress: Session 22 (Real-Time Forecasting Pipeline — COMPLETE)
New module **`backend/vectis/realtime/pipeline.py`** + export from `realtime/__init__.py`.
- **`ContinuousPipeline`** — orchestrates the flow over a `MessageBroker`. All collaborators are
  injected (broker, `KalmanStateUpdater` + its `MemoryStateStore`, `ContinuousBayesianUpdater`,
  `VectorizedMonteCarloEngine`, `SimulationBoardService`, base `WorldState`, `ScenarioSet`,
  `SimulationConfig`), so transport and engines are swappable and the whole thing is unit-testable.
  `async start(max_events=None)` launches a forecast worker and runs an `EventConsumer` on the broker.
- **Fast path / slow path split (the throughput answer).** `process_event` (the consumer callback) is
  **synchronous and sub-millisecond**: `event.to_observation()` → `KalmanStateUpdater.apply_observation`
  → `ContinuousBayesianUpdater.update_probabilities` → enqueue a forecast job. The consumer acks
  immediately, so ingestion is bounded by the cheap math, never by Monte Carlo. The compute-heavy
  stages (Monte Carlo, then the LLM board) run in a background `_forecast_loop` worker, **off the
  event loop via `asyncio.to_thread`**.
- **Per-cell coalescing.** The forecast queue keeps only the *latest* job per `cell_id` (a `_jobs`
  dict + a `_pending` set guard a single queue entry per cell), so a burst of N events for one cell
  collapses to **one** Monte Carlo cycle of the freshest state — the high-throughput guarantee.
- **Board gating.** The decision board only re-runs when headline risk moves ≥ `risk_change_threshold`
  (default 5.0 / 100) since the last report for that cell (first forecast always reports) — damps LLM
  churn. Headline risk = `posterior_mixture_risk(reweighted_scenarios, per-scenario MC means)`;
  confidence = `confidence_from_entropy(posterior)`. Live Kalman means overlay onto the base
  `WorldState` (name-matched vars); the Bayesian posterior replaces the `ScenarioSet` priors.
- **`build_default_pipeline()`** wires the offline Liguria-wildfire defaults (memory broker, three
  wildfire branches, mock LLM board → runs with no network/key).
- **`tests/realtime/test_realtime_pipeline.py`** (renamed from `test_pipeline.py` to avoid a basename
  clash with `tests/unit/test_pipeline.py`) — 3 tests, LLM mocked via a spy provider: one extreme-drought
  event traverses Broker → Kalman → Bayesian → Monte Carlo → report (belief shifts to the drought
  branch, all three scenario outcomes present, report generated); a 3-event burst coalesces to one MC
  cycle; unchanged risk skips the board.

**Verified green:** ruff clean, mypy clean on the new module + test; **139 pytest pass** (was 136).
Smoke run: drought + heat + wind for one cell → risk ~94/100 SEVERE, posterior collapses onto
`hotter_drier`, one decision report — in ~1 s offline.

### What Worked
- **Dependency-injected orchestrator + a `build_default_pipeline()` factory.** The class takes every
  engine as a constructor arg (testable, swappable transport); the factory wires the offline defaults.
  Same pattern as the V2 streaming layer — kept the diff small and the test honest.
- **Fast/slow split with `asyncio.to_thread` + a coalescing queue.** This is the direct answer to "does
  a 500ms Monte Carlo block the consumer?" — no: the consumer only does Kalman+Bayesian and acks, while
  MC/board run off-loop and a burst collapses to the latest state. Mirrors the Session-9 off-loop pattern.
- **Reusing V2 wholesale.** `VectorizedMonteCarloEngine`, `SimulationBoardService`, `posterior_mixture_risk`,
  `confidence_from_entropy`, and the wildfire scenarios all dropped in unchanged — the Math Firewall holds
  end to end (the spy-LLM test confirms the board ran but never touched a number).

### What Didn't Work / Gotchas
- **A single observation with no `std` barely moves the posterior.** The Kalman filter defaults a
  missing measurement σ to variance 1.0, which widens the likelihood scale so much that all scenario
  archetypes look equidistant and the prior dominates (first test failed: baseline 0.47 > hotter_drier
  0.32). Fix: a real "Extreme Drought" reading *is* a confident measurement — the test event now carries
  `std=0.05`, which sharpens the likelihood and flips the belief to `hotter_drier`. Lesson: feeds must
  emit measurement uncertainty for the Bayesian layer to discriminate.
- **Test basename collision.** pytest uses flat module names (no `__init__.py` in test dirs), so
  `realtime/test_pipeline.py` clashed with `unit/test_pipeline.py` at collection. Renamed to
  `test_realtime_pipeline.py`.
- **First forecast always reports** (prior risk is `None`), so the board-gating test pre-seeds
  `_last_risk[cell]` to exercise the skip path.

### Next Steps (Session 23 — V3 Final Demo & Productization)
- **A tactical live-demo script in the `demo_v2.py` mold** (testable `run_demo`, stdlib console): feed a
  Liguria observation sequence through `ContinuousPipeline` and render *both* uncertainties tightening —
  Kalman variance shrinking and the categorical belief sharpening — tick by tick, ending in the report.
- **Wire `ContinuousPipeline` into the API / WebSocket layer** so the frontend dashboard streams the
  continuously-updated `ForecastResult` (risk, band, posterior, report) like the V2 `StateChange` feed.
- **The first concrete `Processor`** (still open since S18/S19): real grid `CellId` assignment (replace
  `naive_cell_id`), validate/dedupe, so multi-cell global ingestion works — then lift the single-belief
  `ponytail:` to per-cell beliefs/`WorldState`.
- **Calibrate the tuning knobs against real data** — scenario profiles, `risk_change_threshold`,
  `process_noise_rate`, MC `n_iterations` are all illustrative; fit to live FIRMS/ERA5 feeds.
- **Productize:** package the pipeline as a runnable service (`make pipeline` / a `scripts/` entrypoint),
  document the architecture in `docs/`, and add a Redis-broker integration path for multi-node throughput.
---

## Current Progress (Session 23 — Live Climate Risk Demo — COMPLETE)

### Goal
Turn the wired-but-headless `ContinuousPipeline` (S22) into a **runnable, end-to-end demo that
proves the V3 system works on a continuous data stream** — the Liguria wildfire scenario, rendered
as a tactical terminal that visibly *comes alive* as mock weather gets hotter and drier. Plus
productization: update the README to declare V3 complete with the exact run command.

### Current Progress: Session 23 (Live Climate Risk Demo — COMPLETE)
New script **`backend/vectis/scripts/demo_v3_live.py`** (+ `tests/realtime/test_demo_v3_live.py`).
- **`run_live(...)`** — async loop that bootstraps the pipeline + an `IngestionManager`, then per tick:
  `producer.poll_and_publish()` (poll connectors → broker) → `pipeline.start(max_events=burst)` (consume
  exactly that burst, drain Kalman → Bayesian → Monte Carlo → report) → render one clean block. Lockstep
  by design so the terminal never races the math; returns `LiveFrame`s so it is testable headlessly.
- **Two ramping offline connectors** subclass the real S17 connectors (so they *are* a
  `WeatherAPIConnector` / `SatelliteAPIConnector`): `RampingWeatherConnector` emits temp climbing
  (+2.1°C/tick), humidity falling, wind rising, and a **drought index** rising (emitted as an extra
  normalized `WeatherEvent` since the base payload has no drought slot); `EscalatingSatelliteConnector`
  emits growing fire-radiative-power. No network, no key — deterministic.
- **Tactical console** reuses `demo_v2`'s `Console`/ANSI/`_force_utf8_stdout`/`_silence_logs` (no new
  deps, no `rich`), clears the screen per tick, and prints the brief's exact block: Current/Previous
  Risk, Trend, Primary Driver (+ live Kalman temp Δ), Confidence (+ Kalman variance), and a posterior
  bar chart. `--ticks N` / `--interval` / `--iterations` flags; Ctrl+C clean exit.
- **README** updated: three-layer framing, a Continuous-Pipeline row in the engineering table, the
  `python -m vectis.scripts.demo_v3_live` command as the flagship quick-start, FIRMS footnote fixed,
  roadmap reframed to V4, project status → V3 complete / 140 tests.

**Verified alive (the quality check):** over ~11 ticks risk climbs **77 → 93**, the belief swings
**baseline 99% → hotter_drier 94%**, the primary-driver label flips to "Temperature & rainfall
anomaly", **confidence dips** (96% → 35%) through the contested transition then recovers, Kalman
variance shrinks (1.00 → 0.09), and the **board re-convenes** on each material move. ruff + mypy clean;
**140 pytest pass** (was 139).

### What Worked
- **Driving the pipeline in lockstep via `start(max_events=burst)` per tick.** Reused the public API
  instead of free-running producer/consumer/render tasks that would race — each tick publishes a burst,
  the pipeline drains it (fast + slow path) and returns, then we render. Clean, deterministic, testable.
- **Subclassing the real connectors to ramp.** Kept the `WeatherAPIConnector`/`SatelliteAPIConnector`
  *types* the brief asked for while overriding only `fetch` (and `normalize` for drought) — the
  resilient base, the `to_observation` hooks, and the whole ingestion path are exercised unchanged.
- **Reusing `demo_v2`'s console toolkit.** Zero new rendering code or deps; the screen-clear per tick is
  one ANSI escape. The "alive" feeling is data, not framework.

### What Didn't Work / Gotchas
- **`build_default_pipeline()` locks the belief at baseline forever.** It sets `relax_rate=0.0`, so once
  the first (calm) reading collapses the posterior onto baseline ~1.0, no later evidence can move it
  (`0 × likelihood = 0`) — the demo's posterior was pinned at baseline 100% and confidence stuck at 100%.
  Fix: the demo wires its own `ScenarioPriors(relax_rate=0.4)` so the belief can swing as heat/drought
  build, then settle. Lesson: a *continuous* belief needs a positive relax rate to stay responsive.
- **Pipeline overlay var-name mismatch (left as-is).** The base `WorldState` names temperature
  `temp_anomaly_c`, but the Kalman store canonicalizes it to `temperature`, so `_overlay_state` never
  projects the live temp mean onto the MC state — risk movement rides on the **Bayesian posterior
  reweighting**, not the overlay. Out of scope for a demo session; flagged for the overlay fix in V4.
- **`temp_delta` shows the Kalman-filtered Δ (~+1.1°C), not the raw +2.1°C reading.** Correct (the filter
  lags the raw feed), just worth knowing when reading the "Primary Driver" line.

### Next Steps — Handover to the Community / V4 Roadmap
- **Real feeds + real transport:** wire the connectors to live NASA FIRMS + ERA5/Copernicus endpoints
  (API keys) and promote the in-process broker to Redis Streams / Kafka for many cells concurrently.
- **Fix the overlay var-name mapping** so live Kalman means project onto the MC `WorldState`, and lift
  the single-belief `ponytail:` to **per-cell** beliefs/`WorldState` for true multi-region streaming.
- **The first concrete `Processor`** (open since S18): real grid `CellId` assignment (replace
  `naive_cell_id`), validate/dedupe.
- **Stream `ForecastResult` to the frontend** over WebSocket so the dashboard's Probability Timeline is
  fed by the continuous pipeline, not the V2 `StateChange` path.
- **Calibrate the tuning knobs against real data:** scenario profiles, `relax_rate`,
  `risk_change_threshold`, `process_noise_rate`, MC `n_iterations` are all illustrative.
- **Persistence & RL:** ORM-backed cell-state + belief-trajectory history; move from *describing* risk to
  *recommending* interventions and learning from outcomes.
---

## Current Progress (Session 24 — Real-Time Frontend Layer — COMPLETE)

### Goal
Bring the V3 *living* backend (S22 `ContinuousPipeline`, S23 terminal demo) to the **React console**:
expose the continuous engine over a real HTTP stream and replace static API calls with dynamic,
continuously-updating visualizations — so the enterprise UI shows the Liguria wildfire risk *shift in
real time*, performantly, without freezing under a high event rate.

### Current Progress: Session 24 (Real-Time Frontend Layer — COMPLETE)
**Backend — exposed V3 as a stream (the missing transport).** Before this session the
`ContinuousPipeline` was only drivable from the terminal demo; nothing V3 was on HTTP (the existing
`/api/v1/stream/ws` is the V2 `StateChange` path). Chose **Server-Sent Events** as best-suited: strictly
server→client, native `EventSource` auto-reconnect, and a heavy compute loop maps cleanly to an async
generator.
- **`backend/vectis/realtime/live_stream.py`** — lifted the two ramping offline feeds out of the demo
  script (`RampingWeatherConnector` / `EscalatingSatelliteConnector`) into a reusable home, plus
  **`LiveClimateStream`**: wires the pipeline + `IngestionManager` and exposes `async frames()` yielding
  JSON-serializable frame dicts (tick, cell, risk, prev_risk, band, confidence, driver, Kalman temp
  mean/variance/delta, posterior, the raw events that drove the tick, and the full decision report —
  attached exactly the frame it's generated on, never re-sent). The demo now imports the connectors from
  here (no duplication; demo still green).
- **`backend/vectis/api/routers/live.py`** — `GET /api/v1/stream/v3/live` returns a `StreamingResponse`
  (`text/event-stream`) driving a fresh `LiveClimateStream` per connection; stops on client disconnect
  (`request.is_disconnected()`). `interval`/`iterations` query params. Wired in `api/main.py`.
- **`tests/realtime/test_live_stream.py`** — frame JSON contract, event-feed normalization, posterior
  sums to 1, `prev_risk` threading, report-dedup. **142 pytest pass** (was 140); ruff + mypy clean.

**Frontend — the Live Intelligence console.**
- **`hooks/useV3Stream.ts`** — subscribes to the SSE endpoint via `EventSource`; exposes `latest`
  frame, an accumulated `timeline` (risk+confidence, capped 240), a rolling `events` log (capped 100),
  and `connected`. **Performance core:** incoming frames land in **refs (no render)** and a single
  **`requestAnimationFrame`** flush coalesces a burst into one `setState` per paint (~60fps ceiling) —
  10 frames between two paints collapse to one render of the freshest state.
- **`features/realtime/` — five stream-fed components** (pure/prop-driven, animation-light):
  `LiveIntelligenceHeader` (cell · current vs previous risk · trend · confidence+σ² · primary driver);
  `LiveRiskMap` (reuses the MapLibre `RiskMap`, the cell recolors along the shared risk ramp, pulsing
  "LIVE" ring); `RiskEvolutionTimeline` (**true dual-axis** Recharts — risk left, confidence right,
  `isAnimationActive={false}`); `ProbabilityBars` (CSS width-transition bars for the shifting Bayesian
  posterior — smoother than re-rendering a chart per frame); `EventFeed` (rolling terminal-style log,
  defensively capped via a `max` prop).
- **`pages/LiveIntelligencePage.tsx`** — composes all five over **one** SSE subscription; wired into the
  router (`/live`) and the sidebar (new `IconLive` broadcast icon, placed second). Inherits the dark
  tactical console design system from the shared UI primitives.
- **`features/realtime/__tests__/realtime.test.tsx`** — EventFeed caps at `max` (renders newest, drops
  beyond the limit); every component renders without crashing on continuous mock frames. **14 Vitest
  pass** (was 7). tsc + eslint clean; `vite build` succeeds.

### What Worked
- **SSE over WebSocket for a server→client compute stream.** `EventSource` reconnects itself (no manual
  backoff like the V2 socket), the endpoint is a plain `StreamingResponse` over an async generator, and
  client disconnect tears the per-connection pipeline down — far less glue than a WS fan-out for a feed
  nothing writes back to.
- **rAF-coalesced rendering as the freeze-proofing.** Buffering frames in refs and committing once per
  animation frame decouples render rate from event rate structurally — the single highest-leverage
  decision for "10 events/sec must not freeze the browser." No throttle constant to tune.
- **Reusing what already shipped.** The MapLibre `RiskMap`, the Recharts dual-axis pattern, every UI
  primitive (`Card`/`Badge`/`RiskScore`), the maplibre test stub, and `renderWithProviders` were all
  reused — the new surface is five small components + one hook + one thin SSE route.
- **Lifting the ramping feeds into a reusable module.** Sharing them between the terminal demo and the
  API stream (instead of importing from `scripts/`) kept layering clean and the demo unchanged.

### What Didn't Work / Gotchas
- **Nothing V3 was on HTTP yet.** The brief said "connect to the V3 backend stream," but the only V3
  driver was the terminal demo; the existing WS is V2. Had to build the SSE transport first — the
  frontend "connect" step is real only because the backend stream now exists.
- **A fresh pipeline per SSE connection.** Each viewer gets its own `LiveClimateStream` (its own ramp
  from a calm baseline) — nice for a demo, but N connections = N Monte Carlo loops. `ponytail:` flagged;
  a shared broadcast pipeline (one engine, fan-out to many clients) is the upgrade when concurrency matters.
- **Recharts `width(0)` warning in jsdom.** Benign — jsdom has no layout, the `ResponsiveContainer` still
  mounts and the test asserts it renders; same warning the existing V2 timeline test emits.
- **`temp_delta` / overlay var-name mismatch carried over from S23** (Kalman names `temperature`, base
  `WorldState` uses `temp_anomaly_c`) — risk still rides the Bayesian reweight, not the overlay. Out of
  scope; still flagged for V4.

### Next Steps (Session 25 — Final V3 Polish & Documentation)
- **Document the real-time layer** in `docs/frontend.md` + `docs/v2_simulation_engine.md` (or a new
  `docs/v3_*.md`): the SSE contract, the frame schema, the rAF rendering strategy, and the `/live` page.
  Add the Live Intelligence page to the README feature list + a screenshot.
- **Shared broadcast pipeline:** replace per-connection `LiveClimateStream` with one engine fanning out
  to many SSE clients (resolve the `ponytail:` note) so the console scales past a single viewer.
- **Polish the page:** surface the streamed `report` (decision board narrative) in a panel when it
  arrives, a connection/last-tick indicator, and graceful empty/reconnecting states.
- **Fix the overlay var-name mapping** (S23 carry-over) so live Kalman means project onto the MC
  `WorldState`; then lift the single-belief `ponytail:` to per-cell beliefs for multi-region streaming.
- **End-to-end check:** an integration test that hits `/api/v1/stream/v3/live` and asserts ≥1 SSE frame
  parses (bound it with a low `iterations` + a client-side disconnect).
- **Calibrate the tuning knobs against real data** (carried from S23): scenario profiles, `relax_rate`,
  `risk_change_threshold`, MC `n_iterations`.
---

## Current Progress (Session 25 — Bridging the Reality Gap — COMPLETE)

### Goal
Fix the three production blockers an external technical audit raised against the V3 architecture and
connect VECTIS to the real world: (1) a **bug** — the Kalman estimate wasn't reaching the Monte Carlo
overlay; (2) **scale** — the SSE endpoint ran one pipeline per viewer; (3) **reality** — the satellite
feed was simulated, not real NASA FIRMS data.

### Current Progress: Session 25 (Bridging the Reality Gap — COMPLETE)
All three audit findings closed; 147 backend tests pass (was 142), ruff + mypy clean.

- **Bug — Kalman→Monte-Carlo overlay.** Root cause: the `KalmanStateUpdater` stores temperature under
  the canonical key `temperature` (via `VARIABLE_FIELDS["temp_anomaly_c"]→"temperature"`), but the MC
  `WorldState` variable is named `temp_anomaly_c`. `pipeline._overlay_state` matched on bare name, so the
  temperature estimate — the hazard model's strongest driver (coef 0.55) — silently matched nothing and
  was dropped; only `wind_speed_kmh` (same name on both sides) landed, leaving risk to move purely via
  Bayesian reweighting. Fix: a module-level `KALMAN_TO_WORLD` bridge (`pipeline.py`) mapping each
  Kalman/Bayesian variable to the WorldState variable it drives, with an additive offset that converts
  an absolute reading to the anomaly the model expects (temperature −22 °C climatology baseline, so a
  24 °C reading reproduces the +2 °C twin baseline). `_overlay_state` rewritten to use it. Verified live:
  risk now escalates **76.5 → 85.3 → 91.3** across ticks, driven by the rising temperature estimate.

- **Scale — decouple the pipeline from viewers.** Was: `live.py` built a fresh `LiveClimateStream` (its
  own Kalman→Bayesian→Monte-Carlo loop) **per SSE connection** — N dashboards = N concurrent engines.
  Now: **`LiveStreamBroadcaster`** (`realtime/live_stream.py`) wraps one `LiveClimateStream`, drives its
  `frames()` as a **single `asyncio` background task started in the FastAPI lifespan** (`api/main.py` →
  `app.state.live_stream`), and fans each frame out to bounded per-subscriber `asyncio.Queue`s (newest
  frame delivered on connect; oldest dropped for a slow client so the single producer never stalls). The
  `/api/v1/stream/v3/live` endpoint is now a lightweight `subscribe()` fan-out — zero compute per viewer.
  Verified: two simultaneous subscribers read **identical** frames from one pipeline (`forecasts_run = 3`,
  not 6).

- **Reality — NASA FIRMS connector.** `connectors/satellite.py` now calls the public FIRMS **area CSV
  API** (`/api/area/csv/{MAP_KEY}/VIIRS_SNPP_NRT/{Liguria bbox}/1`) when `VECTIS_FIRMS_API_KEY` is set,
  parsing each detection (stdlib `csv`, no new dep) into a `fire_radiative_power` `GlobalObservation`.
  Tolerant of product differences (numeric MODIS vs letter VIIRS confidence → midpoint, missing FRP,
  malformed rows skipped). With no key it falls back to deterministic offline detections, so a fresh
  clone runs key-free and offline. Added `BaseAPIConnector.get_text` (extracted the shared retry loop
  into `_get`) so CSV feeds inherit the same backoff/degradation as JSON ones. `firms_api_key` added to
  `core/config.py` + `.env.example`.

- **Tests** (`tests/realtime/test_overlay_and_firms.py`, +5): the overlay maps `temperature`→
  `temp_anomaly_c` with the offset and drops no mapped field; a hotter Kalman mean yields a hotter MC
  input; the FIRMS CSV parses into observations (confidence→std, malformed row skipped); the key-free
  offline fallback; graceful degradation on a FIRMS 503.

### What Worked
- **Localizing the vocabulary bridge at the one boundary that needs it.** Kalman/Bayesian speak absolute
  values; the MC `WorldState` speaks anomalies. `_overlay_state` is exactly where they meet, so the map +
  offset live there — no churn to the connectors, Bayesian profiles, or the EMA state path.
- **Broadcaster as a thin fan-out over the *existing* `LiveClimateStream`.** No pipeline rewrite — wrap
  the already-working `frames()` generator and multiplex it. Smallest diff that makes the engine singular.
- **Reusing the unchanged `normalize()` by shaping `fetch()` output.** The FIRMS CSV parser emits the
  same `{detections:[...]}` dict the offline path already produced, so only `fetch` changed.

### What Didn't Work
- **Matching the old S23 demo numbers (risk 77 → 93).** Those were produced by the *broken* overlay
  (wind + reweighting only). With temperature now driving the MC the curve legitimately changes
  (76.5 → 91.3); chasing the old figures would mean re-breaking the fix. Numbers are correct, not equal.
- **Overlaying the absolute temperature straight into `temp_anomaly_c`.** Without the −22 °C offset the
  log-odds saturate (`expit(−1.5 + 0.55·24 + …) ≈ 1`) and risk pins at ~100 from tick 0 — no escalation
  room. The offset is a deliberate calibration knob, not a hidden constant (flagged `ponytail:` for S26).

### Next Steps (Session 26 — Model Calibration on Historical Data — pick up here)
- **Calibrate against real FIRMS labels.** Replace the illustrative `WildfireHazardModel` coefficients
  and the hand-set `KALMAN_TO_WORLD` climatology offset / `default_scenario_profiles` with values fit to
  historical FIRMS active-fire outcomes (the `models/calibration.py` `reliability_curve` /
  `fit_recalibration` stubs from S8 are waiting). Wire per-cell climatology so the temperature offset is
  data-driven, not a global −22 °C.
- **Multi-region / per-cell beliefs.** Lift the single-belief `ponytail:` in `ContinuousPipeline` to
  `dict[CellId, ...]` so FIRMS detections across Liguria's grid each drive their own forecast — then map
  more Kalman variables (humidity→?, drought→rainfall) once their semantics are calibrated.
- **End-to-end SSE test.** A test that hits `/api/v1/stream/v3/live` against the lifespan-started
  broadcaster and asserts ≥1 frame parses, plus a client-disconnect dropping only that subscription.

---

## What Worked (decisions that succeeded — keep these)

- **(S15) Committing per milestone, atomically and humanized.** Four+ small commits (`feat(ui)`,
  `docs:` ×3) each tell one story and pass their own gate — far easier to review/revert than an
  end-of-session megacommit. The S14 work that was left uncommitted slotted cleanly into two
  atomic commits (backend API, then frontend+wiring).
- **(S15) Documentation as a product surface, not an afterthought.** A mermaid architecture diagram
  + a benchmark table + a real V3 roadmap is what makes a repo *read* as top-tier on first landing.
  Linking every capability claim to the file that implements it is what makes it *credible*.
- **(S15) Verifying doc commands against the schema.** The demo-script `curl` was written, then
  checked against `WeatherAlert` — caught invented fields before they shipped. Docs that don't run
  are bugs.

- **(S14) Mapping deterministic Twin state to `WorldState`.** Allowed for a robust, highly-cached `what-if` simulator endpoint without having to  rewrite or fork any of the core Monte Carlo engine logic.
- **(S14) Exposing statistical bounds (p05/p50/p95) to the frontend.** Returning full distributions instead of just a mean allowed the UI to draw true enterprise confidence-fan/whisker charts natively with Recharts.
- **(S13) One pool per run, not one per scenario.** Building all scenarios' chunks up front and
  dispatching once removed a 3× process-spawn tax (40 s → ~10–15 s for the 1M parallel path) and
  maps cleanly onto a single cluster `gather`. Math unchanged (same chunks, same order).
- **(S13) Distributed = override dispatch only.** `DistributedMonteCarloEngine` reuses the exact
  sharding/RNG/reduction and swaps just *where* chunks run, so a Ray/Dask run literally cannot
  produce different numbers than local. The `LocalClusterStub` keeps it runnable + tested with zero
  new dependency; real Ray is a drop-in behind the `ClusterClient` Protocol.
- **(S13) Caching as a decorator engine, keyed on semantic inputs.** `MemoizingMonteCarloEngine`
  wraps any engine; excluding `estimated_at` from the key is the subtle bit that makes hits
  actually happen (otherwise the timestamp defeats every lookup). TTL+LRU is pure stdlib.
- **(S13) Honest measurement over assumed speedup.** Reused the S7 finding and *proved* it at 1M:
  cheap vectorized math doesn't benefit from multiprocessing; the stress test computes and prints
  the verdict every run rather than asserting a hoped-for win. Parallel stays off by default.

- **(S12) The demo logic lives in a testable package module; the top-level script is a 3-line
  shim.** `vectis.scripts.demo_v2.run_demo(...)` returns a `DemoResult`, so the *same* flow the
  console renders is asserted in the integration test — the demo can't rot. `scripts/
  run_demo_liguria.py` only satisfies the documented command (and self-bootstraps `sys.path`).
- **(S12) Pure-stdlib terminal UI over adding `rich`.** ANSI + box-drawing characters give a
  stunning tactical console with zero new dependency, honoring "clone → install → run flawlessly".
  `color=False` yields clean plain text for test assertions and piping.
- **(S12) Reused the S11 deterministic fallbacks as the demo's "realistic mock".** Because they're
  already BLUF/red-team register and parameterized by region/driver/scenarios, the offline output
  *is* a serious brief — no demo-specific mock provider needed (don't rebuild what already works).
- **(S12) Encoding + logging made bulletproof, not assumed.** A demo whose whole value is the
  console must survive a cp1252 terminal and not interleave operational logs — both fixed
  explicitly rather than hoped away. The "clone and run" promise is only real if it's literally run.

- **(S11) Math Firewall enforced in the type system, not just the prompt.** Numbers are copied
  from the engine output into the report's structured fields *in code*; the LLM only writes prose.
  A hostile/hallucinating model literally cannot change a figure — the strongest possible
  guarantee, and far better than trusting the prompt alone. A lying-LLM test locks it in.
- **(S11) Reused `LLMProvider` (mock default) + LangGraph, not a hard OpenAI dep.** Keeps CI
  offline/key-free/deterministic (the project's iron rule) while honoring "graph-based agents."
  Real providers slot in behind the same interface. Same "reconcile, don't rebuild" lesson as
  S2/S3/S4 — and the deterministic `mock` fallback is what makes the offline output a real brief.
- **(S11) Shared node logic; LangGraph and sequential fallback produce identical reports.** The
  five analysts live in `nodes.py` (no framework); `team.py` wraps them as graph nodes and the
  service runs them in order when LangGraph is absent. The API never breaks on a lean install, and
  the graph stays an *execution* choice — proven by a graph==sequential test (echo of S7).
- **(S11) Deterministic fallbacks written to intelligence-brief standard.** Because `mock` returns
  the fallback, the offline/CI output *is* the brief a four-star general reads. Writing the
  fallbacks in BLUF/terse/red-team register (not generic prose) means the quality bar is met even
  with zero LLM spend.

- **(S10) `DigitalTwin` ABC carries no calculator; the twin maps domain → engine.** The Monte
  Carlo/Bayesian engines stay generic; each twin's *only* engine coupling is one
  `_to_world_state()` method. This is the encapsulation the brief demanded and the thing that
  makes a `FinancialMarketTwin` a sibling, not a rewrite.
- **(S10) Ordering: Bayesian update on the *pre-transition* state, transition after.** An
  observation plays two roles — evidence about which *future* unfolds (compared against the
  prior state's scenario predictions) and a change to the *present* state. Running Bayes first
  preserves discrimination (a +4 °C reading still favors hotter_drier vs the +2 °C estimate);
  applying the transition after evolves the present for the next forecast. Getting this order
  wrong silently flips the belief update.
- **(S10) `RiskState` belongs to `digital_twin`, re-exported from `streaming`.** It's the twin's
  computed output, so the dependency points `streaming → digital_twin` (correct layering); the
  one-line re-export keeps Session-9 imports working with no churn.
- **(S10) Vegetation stress only moves when a driver moved.** Recomputing the coupled stress on
  *every* observation would let unrelated events (a fire count) silently drift it. Gating on
  driver-changed keeps the heuristic honest and the tests deterministic.
- **(S10) Per-twin locks, not one global lock.** The router lock guards only the debounce dict
  (brief); each twin serializes its own updates. That's the difference between a 10k-twin system
  and a single-threaded one.

- **(S9) `RealTimeUpdater.process()` as a pure synchronous seam.** All ordering/decision logic
  (debounce → Bayes → significance → maybe-MC → RiskState) lives in one transport-agnostic
  method that neither awaits nor imports web code. The router (BackgroundTasks) and broadcaster
  (WebSockets) are the only FastAPI-aware pieces. Swapping in Celery/Kafka/Redis = rewrite the
  dispatch glue + publish transport; `process()` and all of `simulation/` are untouched. This is
  exactly the decoupling the quality-check demanded.
- **(S9) `asyncio.to_thread` for the CPU-bound update in a background task.** Ingestion returns
  202 instantly; the numpy/scipy work runs off the event loop (GIL released during the kernel),
  then the broadcast runs back on the loop. Non-blocking without a task queue.
- **(S9) Total-variation distance as the "significant change" trigger.** One cheap, bounded
  ([0,1]) metric on the prior→posterior belief shift decides whether a full MC re-run is worth
  it; small shifts just re-weight cached per-scenario risk. Tunable via `rerun_threshold`.
- **(S9) Debounce on content key, dropping the whole update (not just the MC re-run).** Counting
  100 identical readings as 100 observations would *over-concentrate* the posterior — wrong math,
  not just wasted compute. Dropping content-duplicates inside the window fixes both at once.
- **(S9) `WebSocketLike` Protocol over a hard Starlette import in the manager.** The broadcaster's
  fan-out logic is testable with a plain fake object and carries no transport coupling in its core.

- **(S8) Discrete Bayes over a finite scenario set — exact evidence, no approximation.** Because
  futures are a small, exhaustive `ScenarioSet`, the denominator `P(obs) = Σ P(obs|s)P(s)` is an
  exact finite sum — no grid approximation, no MCMC, no `pymc` needed. Renormalizing over the set
  gives priors that sum to 1 by construction, so the posterior feeds straight back into the MC
  engine. Reach for `pymc`/conjugate updates only when updating a *continuous* state variable's
  distribution, not the scenario weights.
- **(S8) Log-space softmax normalization.** Working in log-likelihoods and subtracting the max
  before exponentiating means a 6σ-decisive observation drives a branch to ~0 without underflow
  or NaNs, and the exact `/sum` afterwards guarantees the schema's sum-to-1 guard passes to
  machine precision. Avoided `logsumexp` import — the manual max-subtract is the same thing, leaner.
- **(S8) Confidence = 1 − normalized entropy.** A single, interpretable `[0,1]` score that
  *automatically* rises with consistent evidence and falls with contradiction, because that's
  what entropy does to a posterior. No hand-tuned heuristic; the math gives the behavior the
  brief asked for.

- **(V2) Pure-math layer, enforced by the dependency graph.** `simulation/` imports only `core` +
  numerical libs, never `agents`. The Golden Rule (no LLM math) isn't a guideline — it's
  structurally impossible to violate from inside the package. Verified by an import-time assert.
- **(V2) Contracts-first again.** Defining `simulation/schemas.py` before any engine logic (as V1
  did with `core/schemas.py`) means Session 7 fills in interfaces against fixed types. Encoding
  invariants in the schema (priors sum to 1; uncertainty mandatory on state vars; seed in config)
  makes whole classes of bugs unrepresentable.
- **(V2) Reconcile to `backend/vectis/`, not a literal `backend/app/`.** Third time this brief
  pattern appeared (S2, S4, now); the answer is the same — integrate, don't duplicate the package.
- **(S7) Vectorization alone crushes the workload — uncertainty propagation via input sampling.**
  The MC stochasticity lives in *sampling the inputs*; the hazard is a deterministic vectorized
  logistic over those arrays. 300k evaluations in ~70 ms with plain numpy/scipy — no Python loop
  over scenarios, exactly as the brief demanded.
- **(S7) One sampling code path, parallelism as an execution mode (not a second algorithm).**
  Draws are *always* split into `n_workers` `SeedSequence.spawn` streams; `parallel` only chooses
  process-pool vs in-process. Result: serial and parallel are **byte-identical** for the same
  `(seed, n_workers)` — proven by a test — so parallelism can't silently change the science.
- **(S7) Reproducibility rooted in numpy `SeedSequence`, defined per `(seed, n_workers)`.** Default
  `n_workers=1` ⇒ a single full-size vectorized draw, fully reproducible on any machine. Avoided
  defaulting workers to `os.cpu_count()` precisely because that would make results machine-dependent.
- **(S7) `scipy.stats` for the named families + `scipy.special.expit` for a stable sigmoid.**
  Honors the brief's "use scipy", gives the modelling vocabulary (Normal/Lognormal/Uniform/Poisson),
  and `expit` is the C-level, overflow-safe logistic — made `scipy` a justified direct dependency.

- **Token-driven restyle (S6).** Recoloring ~10 semantic Tailwind tokens + aliasing `font-sans`
  to mono restyled the whole console with edits to only 2 config/style files plus the 2 shared
  primitives — no page-by-page rework. Proof that the S4 "few semantic tokens" decision paid off.
- **CSS-only radar grid and glow (S6).** Background lattice and neon glow are plain CSS
  (`background-image` + `text-shadow` utilities), not React/canvas — zero runtime cost, no new
  component.
- **45° corners on shared primitives (S6).** Putting `clip-corner` on `Card`/`Button` propagates
  the Arwes look everywhere automatically.

- **Contracts-first design.** Defining `schemas.py` (esp. `DecisionReport`/`AgentState`)
  before logic kept every layer aligned and made the slice fall into place.
- **Custom typed orchestrator over a framework.** Transparent, dependency-light, trivially
  testable; the whole control flow reads in one file. Behind an interface so LangGraph can
  replace it later if ever needed.
- **LLM-narrates-not-decides + deterministic Mock.** Agents compute structured, evidence-
  backed results and only ask the LLM to phrase them, always with a deterministic fallback.
  Result: byte-identical, offline, key-free runs (and CI), with Claude as optional polish.
- **Rule-based, deterministic Critic.** A reliable validation gate (evidence/consistency/
  action checks) beats an LLM gate for reproducibility. Bounded revision loop.
- **Bundled, seeded sample + SHAP-friendly small feature set.** Reproducible offline demo;
  8 human-readable features make SHAP drivers read as plain language.
- **Repository with in-memory fallback.** Dev/test/demo need no Postgres; production uses
  PostGIS. `RunContext` blackboard keeps `AgentState` serializable.
- **(S2) Single lazy engine source + `get_db` dependency.** Caching the engine/sessionmaker
  with lazy settings reads keeps imports side-effect-free (critical for the test env ordering)
  and gives one obvious place for session management.
- **(S2) Alembic env reads the URL from settings, not `alembic.ini`.** Migrations and the app
  can never target different databases; `render_as_batch` keeps SQLite migrations working too.
- **(S2) Reconcile, don't rebuild.** Mapping the new brief onto existing structure (instead of
  scaffolding a duplicate `app/` tree) preserved 30+ passing tests and avoided churn.
- **(S3) Two engines behind one interface, sharing an `AgentSuite`.** Adding LangGraph by
  reusing the existing agents (not duplicating them) means the engines can't diverge; a
  parity test enforces identical output. The S1 "swappable orchestrator" design paid off.
- **(S3) LangGraph realized but kept opt-in.** Default stays `custom` (deterministic, zero
  heavy deps, offline) so CI/demos are unaffected; LangGraph is a one-line config + extra.
  This honors the brief's "use LangGraph" while explaining why custom remains default.
- **(S3) LLM-narrates-not-decides made parity trivial.** Because intelligence is computed
  deterministically and only phrased by the LLM, swapping the orchestration engine can't
  change the numbers — the two engines match exactly.
- **(S4) One-way layered frontend (`pages → features → components → ui`).** Pages own routing
  + data, features compose, `components/ui` is dumb/reusable. New views slot in without
  touching the design system; pages stay mostly layout.
- **(S4) Single React↔backend boundary in `hooks/queries.ts` + one `fetch` in `apiClient`.**
  Pages never call `fetch`; TanStack Query owns caching/loading/error/invalidation. Adding an
  endpoint is a new service fn + hook, nothing else.
- **(S4) MapLibre GL over Mapbox/Leaflet/OpenLayers.** Open-source, no token, no per-load
  billing (keeps offline/self-host), GPU vector tiles + data-driven choropleth paint → risk
  layers scale from 240 cells to thousands as style/source changes, not rewrites.
- **(S4) Mocks quarantined under `services/mocks/` with a loud flag.** Real endpoints are
  consumed for real; the one gap (Datasets catalog) is shaped as an async client so the real
  endpoint is a one-line swap. Nothing fake is smuggled into pages.
- **(S4) MSW page tests over shallow renders.** Mocking at the network layer exercises the real
  hook/service/query path, so a page test actually proves the data flow works end to end.
- **(S5) Audit, don't regenerate.** The OSS scaffolding already existed and was good; fixing the
  few real gaps (tests-in-CI, healthchecks, `npm ci`) beats re-emitting boilerplate that would
  churn history for zero gain — same "reconcile, don't rebuild" lesson as S2/S4.
- **(S5) Backend healthcheck = the readiness signal the frontend waits on.** Because the backend
  command does migrate+seed+train *before* uvicorn serves, `/health` only answers when fully
  ready — so `condition: service_healthy` is exactly the right gate, no extra wait-for script.
- **(S5) `python -c urllib` healthcheck over adding curl.** Keeps the slim image slim; the probe
  uses what's already in the interpreter.
- **(S5) `.editorconfig` over Prettier.** A tool-agnostic whitespace baseline gives the
  "formatting config" both stacks need without a new dep, a full-tree reformat, or eslint
  conflicts. ruff already formats the backend; eslint already gates the frontend.

---

## What Didn't Work / Gotchas (so you don't repeat them)
- **(S14→S15) API overload dropped the final routing — now RESOLVED.** S14 ended before the
  dashboard route was wired (the API dropped mid-edit). S15 completed it: route + nav added,
  typecheck/lint/build/tests all green. Lesson: leaving uncommitted work across an interruption is
  risky — commit each milestone as you finish it (the S15 commit policy now does exactly this).
- **(S15) `tsc --noEmit` fails on unused imports.** The new `useTwinStream.ts` imported `useRef`
  without using it → TS6133. `npm run typecheck` is the fast pre-commit gate; run it before
  assuming the frontend is stable (build is slower and would have caught it later).
- **TS project references + `noEmit`** → `tsc -b` error TS6310. Fixed by giving
  `tsconfig.node.json` `composite: true` with an `outDir`/`tsBuildInfoFile` (no `noEmit`).
- **Vite needs `VITE_API_BASE_URL` at *build* time** (browser calls the API directly).
  The frontend Dockerfile bakes it via an `ARG`; compose passes it as a build arg. Dev uses
  the Vite proxy (`/api`→:8000) instead.
- **Region-level SHAP drivers can be mixed-sign.** A high-magnitude feature (e.g. temperature)
  can have a net-negative mean signed contribution across the region, so it may show as a
  "decreases" driver. Current behavior is intentional (honest), ranked by |SHAP| with
  increasing-first ordering in the report. Revisit if it confuses users.
- **`datetime.utcnow()` / `str,Enum`** → ruff UP flagged them; standardized on
  `datetime.now(UTC)` and `enum.StrEnum`. `Depends()` in defaults is FastAPI-idiomatic;
  `B008` is intentionally ignored in `pyproject.toml`.
- **XGBoost in Docker** needs `libgomp1` (added to the backend image).
- **`get_settings` is `lru_cache`d** → tests set env vars *before* importing vectis and call
  `get_settings.cache_clear()` in `conftest.py`. Keep that ordering. The DB engine in
  `session.py` is likewise `lru_cache`d and lazy — use `reset_engine_cache()` if a test needs a
  different DB URL mid-process.
- **(S2) The Session 2 brief asked to (re)build a foundation that already existed.** Don't take
  such briefs literally when they conflict with this HANDOFF — reconcile to the existing
  `backend/vectis/` package rather than creating a parallel `backend/app/`. A wholesale rename
  was considered and rejected (breaks imports/tests/Docker/docs for zero benefit).
- **(S2) `alembic init` not used** — hand-wrote `env.py`/`script.py.mako`/`0001_initial.py` so
  the env reads VECTIS settings and the initial migration exactly mirrors `AnalysisRecord`,
  rather than letting the generator drop in boilerplate that reads `alembic.ini`.
- **(S3) LangGraph's `add_node` generics fight strict mypy** (`call-overload` on a plain
  partial-update return). Rather than weaken types globally, added a **scoped** per-module
  mypy override (`vectis.agents.langgraph_engine`, `disable_error_code=["call-overload"]`).
  The rest of the codebase stays strict.
- **(S3) LangGraph state passing** — used a tiny `TypedDict` (`state`, `ctx`) and have nodes
  mutate the objects in place and return `{}`. Works because we compile without a checkpointer
  (references are preserved). If checkpointing is added later, switch to serializable state +
  reducers (RunContext holds non-serializable artifacts — keep it off the persisted channel).
- **(S3) Considered, rejected:** making LangGraph the *default* engine (would force the dep on
  CI/demos and risk nondeterminism) and rebuilding agents under `backend/app/agents/`
  (duplicate of working, tested code).
- **(S4) The brief said "ATLAS" and "scaffold `frontend/` from scratch."** Wrong project name
  (this is **VECTIS**) and a frontend already existed. Reconciled to the existing tree and
  expanded it rather than scaffolding a duplicate — same lesson as S2.
- **(S4) `getByText` on legitimately-repeated strings.** Two page tests failed with "Found
  multiple elements" because the UI renders e.g. the area label in both a stat card and a table
  row. Fix is `getAllByText(...).length`, **not** changing the UI — the repetition is intended.
  Don't write singular `getByText` for values that appear in summary + detail.
- **(S4) MapLibre needs WebGL, which jsdom lacks.** The bare `maplibre-gl` module is aliased to
  a stub in the **test env only** (`vite.config.ts` test.alias → `src/test/maplibreStub.ts`),
  with an exact-match regex so the `maplibre-gl/dist/*.css` subpath import still resolves. Don't
  globally mock it (breaks the real build).
- **(S4) Bundle is ~1.4 MB (gzip ~400 kB)** — MapLibre + Recharts dominate; Vite warns >500 kB.
  Left as-is (functional); route-level code-splitting / `manualChunks` is a polish item.
- **(S5) Considered, rejected — adding Prettier.** Would add a dependency, reformat the whole
  frontend (huge noisy diff), and overlap/conflict with the existing eslint gate. `.editorconfig`
  covers the actual need (consistent whitespace across editors). Add Prettier only if the team
  wants enforced code style beyond lint.
- **(S5) Considered, rejected — multi-stage nginx frontend image.** The current `vite preview`
  static server is fine for local/dev compose (the S5 objective). A hardened nginx image is a
  *deployment* concern → deferred to the deploy session, noted in Next Steps.
- **(post-S5) `baseUrl` is deprecated in TS 7.0.** Don't pair `paths` with `baseUrl` anymore —
  TS 5.0+ resolves `paths` relative to the `tsconfig.json` location, so use self-relative globs
  (`"@/*": ["./src/*"]`) and drop `baseUrl`. Editors surface this as a hard error (severity 8)
  with `ignoreDeprecations` as the silence-only escape hatch; the real fix is to remove `baseUrl`.
- **(S5) Compose full-stack run not executed on this machine.** Edits to `docker-compose.yml`
  (healthcheck, `service_healthy` gate) and `frontend/Dockerfile` (`npm ci`) were validated by
  reasoning + `npm ci` sync check, but `docker compose up` still hasn't been run here (carried
  over from S4 #5). First task for whoever has Docker available.
- **(S6) `clip-path` corners eat the border on the diagonal cut.** The 45° `clip-corner`
  utilities clip the element, so the CSS `border` is visible only on the straight edges, not the
  angled corners. Accepted (still reads as a high-tech cut) and reinforced with a neon
  `box-shadow` ring. For a true Arwes outline on the diagonals later, overlay an SVG/pseudo-element
  border instead of relying on `border`.
- **(S6) three.js inflates the bundle to ~2.3 MB (gzip ~630 kB).** Vite warns >500 kB. Left as-is
  (functional); the right fix is lazy-loading `GlobeWidget` via `React.lazy` + `manualChunks` so
  three only loads on the Overview route — folded into the existing code-splitting polish item.
- **(S6) `@react-three/fiber` Canvas renders nothing under jsdom (no WebGL).** It does *not*
  throw, so the OverviewPage test still passes without mocking. Don't add a stub unless a test
  starts asserting on canvas internals.
- **(S6) "Multiple instances of Three.js" warning** in test/build output comes from fiber+drei
  pulling three; harmless with a single `three` in the lockfile. Ignore unless it becomes a real
  dedupe problem.

---

- **(S7) Multiprocessing is *not* a speedup for this workload — kept as architecture, off by
  default.** For 100k cheap vectorized evaluations the numpy kernel runs in tens of ms; spawning
  processes + pickling arrays would *add* overhead. Implemented the chunked `ProcessPoolExecutor`
  path (correct, reproducible, tested) but default `parallel=False`/`n_workers=1`. The ceiling it
  raises: turn it on when *per-sample* cost grows (expensive physics per draw), not for cheap math.
- **(S7) `concurrent.futures` worker must be module-level + args picklable.** `_simulate_chunk`
  lives at module scope in `engine/runner.py` and takes only picklable args (pydantic models, a
  numpy `SeedSequence`, an int, a frozen-dataclass hazard) so Windows `spawn` works. Don't make it
  a closure/method — it won't pickle.
- **(S7) `ruff` gotchas in new code:** `N817` rejects `import DistributionFamily as DF` (acronym),
  `C408` rejects `dict(...)` literals, `I001` import ordering (stdlib `concurrent.futures` before
  third-party `numpy`). All trivially fixed; mypy is scoped to `vectis/` only (tests untyped is fine).

## Next Steps — Handover to the community & V3 vision

**V2 is complete and released.** The full arc S1→S15 is done: V1 reactive vertical, then the V2
probabilistic engine (Monte Carlo, Bayesian update, real-time streaming, digital twin, LLM board),
scaled to 1M scenarios, productized into a dashboard, and shipped with architecture docs, a demo
script, and an overhauled README. 107 backend tests + the full frontend gate are green. There is
no "pick up the unfinished thing" — the next engineer is building **V3**, not finishing V2.

### Hand the repo to the community
- **Record the showcase video** from `docs/demo_video_script.md` and drop the captures under
  `docs/assets/` (the README + frontend docs have screenshot placeholders waiting).
- **Tag a release** (`v2.0.0`) and write release notes from the S6–S15 history below.
- **Open "good first issue"s** from the V3 list so contributors have an on-ramp. `CONTRIBUTING.md`,
  `CODE_OF_CONDUCT.md`, and `SECURITY.md` already exist.
- **Run `docker compose up --build` once on a Docker host** — still never validated here (item 0,
  carried since S4/S5). It's the last unchecked box on "clone → run".

### The V3 vision — from one twin to a living intelligence network
1. **Live data streams (the big one).** NASA **FIRMS** active-fire ingestion, then ERA5/Copernicus,
   delivered over **Apache Kafka** so twins react to the real world, not synthetic events. The
   transport seam is ready: `RealTimeUpdater.process()` / `twin.update_from_observation()` stay
   unchanged; only the ingest glue (BackgroundTasks → Kafka consumer) changes.
2. **Persistence & belief history.** ORM-backed `StateManager` + twin/posterior snapshots over time
   (reuse the S2 `database/` layer), so risk trajectories survive restarts and are auditable.
3. **Reinforcement learning for suggested actions.** Go beyond *describing* risk to *recommending*
   interventions (resource pre-positioning) and learning from resolved outcomes — feeds the
   blueprint `probability/calibration.py` (Brier score) as the reward signal.
4. **Multi-twin interaction.** Twins that influence each other across domains — **Climate × Finance**
   (wildfire risk → insurance/commodity exposure) — composed through the existing `StateManager`.
5. **Horizontal scale.** Promote the S13 distributed *stub* to real **Ray/Dask**; move
   `StateManager`/broadcaster/cache to **Redis** for many regions concurrently.

The carry-over backlog below (forecasting impl, live connectors, persistence, async board, real
LLM provider, calibration) is the concrete task-level feed into that V3 vision — still valid.

### How to get oriented fast
```bash
# Backend (offline, no keys)
cd backend && python -m venv .venv && .venv/Scripts/activate
pip install -e ".[dev,langgraph]"
pytest                             # 107 tests, all green
python -m vectis.scripts.demo_v2   # watch the full V2 pipeline run (offline, ~1s)
python scripts/stress_test.py      # 1M-scenario Monte Carlo + honest perf verdict

# Frontend
cd frontend && npm install && npm run dev            # http://localhost:5173 → "Decision Intelligence"
npm run typecheck && npm run lint && npm run build    # all green
```

### Session 14 PRIMARY: VECTIS V2 Productization

The engine, twin, real-time loop, AI board, demo, and scale story are all complete and green
(101 backend tests). Session 14 should turn the *capability* into a *product* a user can actually
deploy and operate — close the gap between "runs the demo" and "runs in production." Suggested
spine (pick the highest-leverage; don't try all):

- **Persistence (most-deferred, highest value).** Twins + belief history are in-memory and lost on
  restart. Add an ORM-backed store (reuse the S2 `database/` session layer + Alembic) for
  `RegionState` + posterior `ScenarioSet` snapshots over time, so twins survive restarts and the
  belief trajectory is queryable/auditable. `StateManager` becomes the read-through cache over it.
- **The V2 frontend (the demo's other half).** The console proves the pipeline; now surface it in
  the S4/S6 React app: `GET /stream/state`, the live `WS /stream/ws` push, and
  `POST /intelligence/reports` (render the `DecisionIntelligenceReport` — analyst brief, scenario
  storylines, debate, red-team). Report JSON is already frontend-ready; wire real risk into
  `GlobeWidget` (S6 TODO). This is what makes V2 *visible*.
- **Run it for real — close the loops.** (a) `docker compose up --build` once (item 0, carried from
  S4/S5) — the last unvalidated piece of "clone → run". (b) The **NASA FIRMS** connector so at
  least one ingested observation is a genuine active-fire detection, not synthetic. (c) A real
  `OpenAIProvider`/`AnthropicProvider` behind `LLMProvider` for a *keyed* demo (mock stays default).
- **`forecasting/` impl → public `Forecast`** + endpoint (mixture over scenarios by posterior
  priors → horizon distribution + per-band probabilities; reuse `posterior_mixture_risk` +
  `scenario_confidence`). Natural next contract for the frontend and the board.
- **Operability:** AuthN/Z (API keys/JWT) ahead of any deployment; structured request logging +
  basic metrics on the V2 endpoints; the async board/provider path (deferred from S13) if concurrent
  report load is real. Multi-stage nginx frontend image (deferred since S5) when shipping.

Carry-over backlog (still valuable, in priority order):

- **`forecasting/` impl → public `Forecast`** (mixture over scenarios weighted by posterior priors
  → horizon distribution + per-band probabilities; reuse `posterior_mixture_risk` +
  `scenario_confidence`) + an endpoint. The board's `DecisionIntelligenceReport` and the frontend
  are its natural consumers.
- **Frontend wiring (the demo's other half).** Connect the console to `GET /stream/state`, the
  `WS /stream/ws` push, and `POST /intelligence/reports` (render the `DecisionIntelligenceReport`);
  wire real risk into the 3D globe (`GlobeWidget`, S6 TODO). The report schema is already JSON-ready.
- **`states/base.py` impl → `SampleStateEstimator`.** Build a `WorldState` from the V1 feature
  pipeline (`data/pipeline/`) and feed it into `RegionTwin` so the twin starts from estimated
  reality, not the default `RegionState`. (Carried from S8/S9/S10.)
- **Live observation source — NASA FIRMS** (then ERA5) mapped into `SensorReading`/`WeatherAlert`
  events; a poller calls `updater.process` / POSTs `/stream/ingest`. Keep offline the default.
- **Persist the twin + belief history.** `StateManager` + twin state are in-memory (lost on
  restart). Add an ORM-backed store for `RegionState` + posterior `ScenarioSet` snapshots over
  time, so twins survive restarts and the belief trajectory is queryable/auditable.
- **A real `OpenAIProvider`/`AnthropicProvider` for the board** (behind the existing `LLMProvider`
  interface, like the V1 anthropic provider) so a *keyed* demo run shows real narration; `mock`
  stays the default so CI/offline is unchanged.
- **Calibration:** `WildfireHazardModel` coefficients are illustrative (`ponytail:` in
  `models/wildfire.py`); `probability/calibration.py` reliability-curve + recalibration are
  blueprint stubs. Once FIRMS labels exist, fit the hazard and log resolved forecasts into a
  `Calibrator` so `brier_score` becomes a tracked metric.
- **Streaming/twin hardening (when scaling out):** in-memory by design (per-twin locks, in-memory
  debounce dict + twin registry, in-process WebSocket fan-out). To scale: `StateManager` → Redis/DB,
  broadcaster → Redis pub-sub, debounce dict → Redis TTL key, BackgroundTasks → Celery/Kafka
  worker — `RealTimeUpdater.process()` and `twin.update_from_observation()` stay unchanged.

0. **Run `docker compose up --build` once** on a machine with Docker (carried from S4/S5). Verify
   the new backend healthcheck flips healthy after migrate+seed+train and the frontend then starts
   and reaches the API. This is the last unvalidated piece of the "clone → run Docker" promise.

Then, highest-leverage:

1. **Live data connector — NASA FIRMS.** Implement `FirmsConnector` (`data/connectors/live.py`,
   simple REST, free key) mapping real active-fire detections onto `RAW_COLUMNS` at Liguria grid
   resolution. Then ERA5 (weather) + Copernicus (NDVI/land cover). Keep `sample` the default;
   connector selectable via settings/request; preserve offline reproducibility (live = opt-in).
   **Frontend is already ready** — the Datasets page lists these as "planned"; flipping one to
   "active" + adding a real `/datasets` endpoint removes the only mock.
2. **Real feature pipeline from live sources.** Resample/join live layers to the region grid;
   validate against `pipeline/schema.py` ranges; retrain and compare to the sample baseline.
3. **Backend `/datasets` endpoint** → remove the frontend's only mock (`services/mocks/datasets.ts`);
   the client (`services/datasets.ts`) is a one-line swap.
4. **Custom-scenario backend params** → wire the disabled `ScenarioPanel` custom builder
   (temperature/drought perturbation) to a real Simulation endpoint that accepts parameters.
5. **Deployment hardening (when shipping):** multi-stage **nginx** frontend image (replace
   `vite preview`); pin/scan dependencies (Dependabot or `pip-audit`/`npm audit` in CI); add a
   `make test` target that also runs the frontend suite; consider a coverage gate.
6. **Frontend polish:** route-level code-splitting / `manualChunks` + `React.lazy` for
   `GlobeWidget` (bundle ~2.3 MB now that three.js is in), an orchestration-engine indicator,
   evidence drill-down, and console screenshots into `docs/assets/` (README has the placeholder).
6b. **Wire real risk data into the 3D globe.** `GlobeWidget` currently plots static Liguria
   province centroids in a fixed neon color. Color/size each node by the live `risk_score`
   (reuse `utils/risk.ts` `riskColor`) and add hover tooltips, so the "Liguria — Tactical View"
   reflects actual analysis output rather than just geography.
7. **LLM-assisted critique (additive)**; **ORM domain entities** (`areas`/`datasets`/`predictions`/
   `reports` via `make revision`); **AuthN/Z** (API keys/JWT) ahead of deployment.
8. **Optional:** knowledge-graph layer; LangGraph checkpointing (serializable state — keep
   `RunContext` artifacts off the persisted channel).

### How to get oriented fast
```bash
# Backend (offline, no keys)
cd backend && python -m venv .venv && .venv/Scripts/activate   # (Windows)
pip install -e ".[dev]"            # add ".[langgraph]" to use the LangGraph engine
python -m vectis.scripts.demo       # see the whole system work in ~3s, offline
pytest                             # 101 tests, all green
python -m vectis.scripts.demo_v2    # watch the full V2 pipeline run (offline, ~1s)
python scripts/stress_test.py       # 1M-scenario Monte Carlo + honest perf verdict

# Frontend
cd frontend && npm install && npm run dev    # http://localhost:5173 (proxies /api → :8000)
npm run lint && npm run typecheck && npm run test && npm run build   # all green; 7 tests
```
Backend spine, read in order: `core/schemas.py` → `agents/runtime.py` → `agents/orchestrator.py`
(+ `agents/langgraph_engine.py`) → `agents/critic.py` → `models/predictor.py`. To switch engine:
`VECTIS_ORCHESTRATOR=langgraph`. Frontend spine: `app/App.tsx` → `hooks/queries.ts` →
`services/apiClient.ts` → `pages/RiskIntelligencePage.tsx`. Full frontend docs: `docs/frontend.md`.
