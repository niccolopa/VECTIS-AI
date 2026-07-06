<div align="center">

# ▲ VECTIS

**Real-Time Probabilistic Decision Intelligence Platform**

*Open-source. Turns a live stream of real-world observations into explainable
**distributions over possible futures** — not single-number guesses — and narrates
them with an auditable AI board whose numbers are produced entirely by deterministic math.*

[![CI](https://github.com/your-org/vectis/actions/workflows/ci.yml/badge.svg)](.github/workflows/ci.yml)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](backend/pyproject.toml)
[![Backend tests](https://img.shields.io/badge/backend%20tests-320%20passing-brightgreen.svg)](backend/tests)
[![Scale](https://img.shields.io/badge/Monte%20Carlo-1M%20scenarios%20in%20~0.8s-00ffd5.svg)](docs/v2_simulation_engine.md)

</div>

---

<img width="1918" height="906" alt="image" src="https://github.com/user-attachments/assets/36b80817-4367-4a6e-95da-5ad4f5ef74e8" />

<div align="center"><sub><b>The V4 Global Terminal</b> (<code>/terminal</code>) — the planet-scale system: a worldwide
H3 grid painted with real per-hazard screening scores across every continent, with tiered deep
analysis on cells that real activity promotes. This is the global system, not the California demo.</sub></div>



## What VECTIS is

Most "AI risk" tools hand you one number and ask you to trust it. VECTIS refuses to.
It simulates **thousands to millions of possible futures**, weights them by a
continuously-updated belief, and shows you the full distribution — then lets an AI
analyst board explain it *without ever touching the math*.

VECTIS is built in three layers:

- **V1 — Reactive Decision Intelligence.** Answers *what is happening · why · what
  could happen next · what to do*, via a data pipeline, ML with **SHAP**
  explainability, and a multi-agent system with a mandatory **Critic**.
- **V2 — The Simulation & Forecasting Engine.** Answers a harder question: *given the
  current state of the world, what are all plausible futures, and with what
  probability?* It produces **distributions over outcomes** via Monte Carlo, updates
  them in real time with **Bayesian inference**, and runs a **digital twin** of the
  region you care about.
- **V3 — The Continuous Real-Time Pipeline.** Closes the loop into one living stream:
  live connectors (weather · satellite/FIRMS) feed a broker, a **Kalman filter** tracks
  each cell's state *with uncertainty*, a **continuous Bayesian** belief shifts as
  evidence mounts, and the Monte Carlo engine + analyst board re-fire whenever risk
  moves materially — a **fast path** (sub-ms Kalman+Bayesian) decoupled from a **slow
  path** (Monte Carlo + LLM board) so ingestion never blocks on simulation.

The first complete vertical is **Climate (wildfire) Risk Intelligence**, demoed
end-to-end on **California, USA**. It runs **fully offline** with a deterministic mock
LLM and a bundled dataset — **no API keys required**.

### Two analysis systems in one console — don't confuse them

VECTIS ships **one primary system and one archived origin demo**. They look similar but
are **not** the same system, and one is **not** a subset of the other:

| | **Global Terminal** (V4 — the primary system) | **California Case Study** (Origin Demo · V1 Archive) |
|---|---|---|
| Where | Sidebar → **Global Terminal** (`/terminal`) | Sidebar → the collapsed **Origin Demo · V1 Archive** section → *California Case Study* / *Case Study Reports* |
| Scope | **Worldwide** H3 grid, every continent | **California only** — nowhere else |
| Data | Live **FIRMS · USGS · GDACS · Open-Meteo** feeds | A fixed **240-cell California sample** from Session 1 |
| Engine | Tier-0 screening → Tier-1 Monte Carlo → Tier-2 board, demand-driven | A scikit-learn **logistic regression** → 6-agent board with **SHAP** |
| Deep report | On any cell **the grid has data for**, when real activity promotes it to T1/T2 | On the **California sample only** — the model was never trained anywhere else |

The Case Study is kept because it was VECTIS's **origin** (Sessions 1–15) and it remains
the only surface demonstrating a **trained ML model with real SHAP attribution** — a
genuinely different capability from the terminal's closed-form driver attribution. It is
**California-bound by construction**: its ML model was fitted on that one sample and cannot
be pointed at another region without retraining. The **Global Terminal is region-agnostic
by design** and is the system to use for planet-scale, live analysis. The archive section
is collapsed by default and each archived page carries an explicit banner, so the two are
never mistaken for one another. (The former V2 "Decision Intelligence" dashboard, V3 "Live
Intelligence" console, and the Maps page were retired in Session 42 — the Global Terminal
does everything they did, on live data.)

---

## The engineering that makes it serious

| Capability | What it means | Where |
|---|---|---|
| **Vectorized Monte Carlo** | 100k–1M scenarios per run in pure NumPy/SciPy, reproducible per `(seed, n_workers)` | [`simulation/engine/runner.py`](backend/vectis/simulation/engine/runner.py) |
| **Bayesian belief update** | Each observation shifts a posterior over scenarios in log-space (exact, not heuristic) | [`simulation/probability/bayesian.py`](backend/vectis/simulation/probability/bayesian.py) |
| **Digital twin** | A self-updating `RegionTwin` holds state + belief and re-runs only when beliefs move materially | [`digital_twin/`](backend/vectis/digital_twin/) |
| **Real-time stream** | `POST /stream/ingest` returns **202 immediately**; CPU-bound math runs off the event loop; results pushed over WebSocket | [`streaming/`](backend/vectis/streaming/) |
| **Continuous pipeline (V3)** | Live connectors → broker → **Kalman** state estimation → **continuous Bayesian** belief → Monte Carlo → report, as one streaming loop with a fast/slow path split and per-cell burst coalescing | [`realtime/pipeline.py`](backend/vectis/realtime/pipeline.py) |
| **The Math Firewall** | LLMs **never** compute. Every number on a report is copied from the engine; the AI writes only prose | [`agents/board/`](backend/vectis/agents/board/) |
| **TTL + LRU caching** | Identical re-runs return in microseconds (~6000× faster) | [`simulation/caching.py`](backend/vectis/simulation/caching.py) |
| **Distributed-ready** | A Ray/Dask abstraction (override *dispatch* only) with a runnable local stub — zero heavy deps | [`simulation/engine/distributed.py`](backend/vectis/simulation/engine/distributed.py) |

> **The Golden Rule of V2:** all probabilistic computation lives in deterministic
> libraries behind explicit interfaces. Nothing under `simulation/` imports the agents
> layer. LLMs re-enter only as *Analyst* agents that *read* the numbers. The
> "LLM-narrates-not-decides" discipline is enforced at the type boundary.

<img width="1918" height="905" alt="image" src="https://github.com/user-attachments/assets/63445b8a-f8c1-40b9-9b22-7a0c8040b7d7" />
<img width="1912" height="903" alt="image" src="https://github.com/user-attachments/assets/571ff80c-2364-4fbd-89e6-0721181a7aec" />
<img width="1918" height="907" alt="image" src="https://github.com/user-attachments/assets/50b11752-f074-4811-ab28-09ff9449b1bc" />

<div align="center"><sub><b>The Origin Demo · V1 Archive — California Case Study</b> (Case Study → Reports).
All three views above are the original Session-1 reactive pipeline: a logistic-regression model
trained on a fixed 240-cell <b>California</b> sample, its SHAP-attributed drivers, and the 6-agent
decision board. <b>This is California only</b> — it is the <a href="#two-analysis-systems-in-one-console--dont-confuse-them">archived V1 origin demo, not the
global V4 Terminal</a>, and does not represent worldwide capability.</sub></div>



---

## Performance & Scale

VECTIS's engine is **vectorized**, not looped. The stress test (`make stress`, see
[`backend/scripts/stress_test.py`](backend/scripts/stress_test.py)) runs **1,000,000
scenarios × 3 scenario branches = 3,000,000 trajectory evaluations** and reports the
honest numbers — measured on a 12-core dev machine:

| Mode | 1M × 3 branches | Throughput | Peak memory |
|---|---|---|---|
| **Single-thread vectorized NumPy** | **~0.8 s** | **~3.6 M evals/s** | ~72 MB |
| Multiprocessing (11 workers) | ~10 s | ~0.3 M evals/s | — |
| Distributed adapter (local stub) | ~0.7 s | ~4.3 M evals/s | — |
| Cache warm hit | ~0.0001 s | — | — |

**The honest finding (and we print it every run):** for *cheap* per-sample math, a
single NumPy thread **beats** multiprocessing by ~12× — process spawn and pickling the
result arrays back cost more than the compute they parallelize. So parallelism stays
**off by default**; it pays off only when per-sample cost grows (expensive physics).
We measured it and documented it rather than assuming a speedup.

Reproducibility is guaranteed per `(seed, n_workers)` via
`numpy.random.SeedSequence.spawn`: **serial, multiprocessing, and the distributed stub
all produce byte-identical results**. Details: [`docs/v2_simulation_engine.md`](docs/v2_simulation_engine.md) §10.

**At planet scale (V4).** The engine above is one cell; the V4 stress test (`make
global-stress`) drives the *real* shared compute loop — screen → tier → Monte Carlo T1 →
board T2 — under synthetic worldwide activity at increasing intensity (up to **40,000
cells crossing the threshold at once** over a 40k-cell global hot set). Measured on the
same 12-core machine, production budgets: full sweep + first deep-analysis batch **< 1.5
s**, memory **~32–38 MB** for 40k active cells, and the hard per-cycle budgets (64 Monte
Carlo forecasts, 5 board narrations) **never breached** — a storm degrades into a deeper
queue, never a melted cycle. The **T2 board/LLM narration budget is the tightest
bottleneck** (it drains ~13× slower than T1). Honest ceilings, framed against the
hardware: **[`docs/scale_limits.md`](docs/scale_limits.md)**.

---

## Architecture

The full real-time pipeline — **External data → Real-Time Updater → Digital Twin →
Bayesian Update → Monte Carlo Engine (+ cache) → LangGraph Analyst Board → React
Dashboard** — with mermaid flow and sequence diagrams and a component-to-code map:
**[`docs/v2_architecture.md`](docs/v2_architecture.md)**.

```
   External events (sensors · weather alerts · FIRMS*)
                       │ POST /stream/ingest (202)
                       ▼
            RealTimeUpdater ──► RegionTwin (state + belief)
                       │              │ Bayesian update
                       │              ▼
                       │     Monte Carlo Engine ◄──► TTL/LRU cache
                       │     100k–1M vectorized scenarios
                       ▼              │
              WebSocket push    RiskState + per-scenario distributions
                       │              │ (read-only numbers · Math Firewall)
                       ▼              ▼
            React Console ◄──── LangGraph Analyst Board
       (Global Terminal drill-down: scenario     (Analyst→Scenario→
        whiskers · posterior · AI Brief)          Debate→Red-Team)
```
<sub>*Weather + FIRMS-style active-fire connectors now feed the V3 continuous pipeline
([`realtime/`](backend/vectis/realtime/)); see `demo_v3_live`.</sub>

| Layer | Stack |
|---|---|
| Simulation | **NumPy · SciPy** (vectorized Monte Carlo, Bayesian inference) |
| Backend | Python 3.11, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, **h3** (global grid), structlog |
| Agents | LangGraph board + custom DAG (two engines); Anthropic Claude or deterministic mock |
| ML (V1) | scikit-learn, XGBoost, **SHAP** |
| Frontend | React 18, TypeScript, Vite, Tailwind, TanStack Query, **Recharts**, MapLibre GL, **h3-js** |
| Infra | Docker Compose, GitHub Actions CI, ruff + mypy + pytest |

---

## Quick start

### Option A — the offline demos (no Docker, no API key)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

python -m vectis.scripts.demo_v3_live  # V3: LIVE continuous stream — risk shifts in real time
python -m vectis.scripts.demo_v2       # V2: full simulation pipeline as a tactical console
make stress                            # 1,000,000-scenario Monte Carlo + honest verdict
python -m vectis.scripts.demo          # V1: one reactive Decision Report
```

`demo_v3_live` is the flagship: mock weather + satellite feeds get hotter and drier each
tick, and you watch the California wildfire risk climb, the scenario belief swing from
*baseline* to *hotter & drier*, and the decision board re-convene — a living system, not a
static report. Ctrl+C to stop, or bound it with `--ticks N` (e.g. `--ticks 12 --interval 1`).

### Option B — the live console

```bash
# terminal 1 — backend API at :8000
cd backend && make api

# terminal 2 — frontend at :5173
cd frontend && npm install && npm run dev
```

Open <http://localhost:5173> and click **Global Terminal** in the sidebar — the worldwide
H3 grid paints live screening scores, the tape streams real detections, and clicking any
cell opens its honest drill-down brief (per-feed LIVE/SYNTHETIC badges included).

### Option C — Docker (the lean single-node stack)

```bash
cp .env.example .env
make up          # PostGIS + Redis + Sluice ingestion gateway + backend + frontend
```

This is the whole production topology on one box (validated end-to-end). Redis backs the
shared state/broker seams and the Sluice is the optional feed gateway; horizontal scale
(N backend replicas sharing this same Redis + PostGIS) is **available, not required**.
Full write-up: **[`docs/deployment.md`](docs/deployment.md)**.

> Use a real LLM by setting `VECTIS_LLM_PROVIDER=claude` and `VECTIS_ANTHROPIC_API_KEY`
> (`pip install -e '.[llm]'`). The LLM only *narrates* already-computed numbers.

> **Persistence & history (V4):** the durable belief-history + playback layer needs
> **Postgres + PostGIS**. Docker (`make up`) applies the Alembic migrations and seeds
> automatically; for a **local** database, run `make migrate` (`alembic upgrade head`,
> migrations `0001`→`0003`) once against your `VECTIS_DATABASE_URL`. The offline demos
> (Option A) and the live streaming dashboard (Option B) run **fully in-memory** and need
> no database.

---

## The V4 Global Terminal

The flagship of the V4 arc (Sessions 30–40) is the **Global Terminal** at `/terminal` (the
hero screenshot at the top) — the **planet-scale** system, distinct from the V1 California
demo:

- **Worldwide H3 grid.** Real per-hazard screening scores across every continent, painted
  from a viewport-scoped tile server that rolls fine cells up to coarse by max-per-hazard.
- **Demand-driven tiered compute.** One shared loop per tick: cheap **Tier-0** screening
  over the whole active set → budgeted **Tier-1** Monte Carlo + Bayesian deep analysis →
  **Tier-2** board narration — bounded by *attention + real events*, never viewer count ×
  grid size (50 viewers and 5 viewers do identical work).
- **Multi-hazard.** Wildfire · flood · earthquake · cyclone, all flowing through the *same*
  Monte Carlo engine, Bayesian updater, and analyst board behind a shared `HazardModel` seam.
- **Drill-down that is honest by construction.** The `RegionBriefPanel` shows a flat
  "screening estimate only" for un-promoted (T0) cells and full p05/p50/p95 whiskers +
  posterior + analyst brief only for cells real activity promoted to T1/T2.
- **Memory + history.** A durable, queryable belief-trajectory store (PostGIS) under the
  hot tier, bounded retention/roll-up, and a scrubbable **playback** mode that is
  unmistakably amber-not-live.

Scale ceilings: **[`docs/scale_limits.md`](docs/scale_limits.md)**. Deployment:
**[`docs/deployment.md`](docs/deployment.md)**. A maintainer's 2-minute showcase script:
[`docs/demo_video_script.md`](docs/demo_video_script.md).

> **Not to be confused with the V1 California Case Study** (the sidebar's collapsed
> *Origin Demo · V1 Archive* section — the three lower screenshots). That is the
> original reactive pipeline on a fixed California sample; see
> [Two analysis systems](#two-analysis-systems-in-one-console--dont-confuse-them).

---

## Beyond V4 — the open frontier

**V4 (Sessions 24–40) is complete and tagged `v4.0.0`** — see
[Project status](#project-status) below. The platform now runs a global H3 grid against
live multi-source feeds, with demand-driven tiered compute, multi-hazard models, and a
durable queryable history: the original V4 goals of *real feeds at scale*, *Redis-ready
transport*, and *persistence & history* are delivered, stress-tested at planet scale, and
shipped as a validated single-node stack. The longer-horizon frontier it is built toward,
still open past V4:

- **Reinforcement learning for suggested actions.** Move beyond *describing* risk to
  *recommending* interventions (where to pre-position resources) and learning from outcomes.
- **Multi-twin interaction.** Cells/twins that influence each other across domains —
  e.g. **Climate × Finance** (wildfire risk → insurance/commodity exposure).
- **Horizontal scale.** Promote the Redis-ready state/broker/cache seams and the
  distributed stub to real **Ray/Dask** clusters for full global concurrency.

Full engineering history and next steps: **[`HANDOFF.md`](HANDOFF.md)**.

---

## Project status

- **V1 (Sessions 1–6):** complete reactive vertical — pipeline, ML+SHAP, agents, console.
- **V2 (Sessions 6–15):** complete — Monte Carlo engine, Bayesian update, real-time
  streaming, digital twin, LangGraph board, 1M-scenario scale, and the dashboard.
- **V3 (Sessions 16–23):** complete — global event schema, resilient connectors,
  broker/producer/consumer streaming, Kalman state estimation, continuous Bayesian
  belief, and the `ContinuousPipeline` that unites them into one live stream (`demo_v3_live`).
- **V4 (Sessions 24–40):** **complete — tagged `v4.0.0`.** Global H3 grid with sparse
  state; live multi-source ingestion (weather · FIRMS · USGS · GDACS); **demand-driven
  tiered compute** (cheap global Tier-0 screening → budgeted Tier-1 Monte Carlo deep
  analysis → Tier-2 board narration, one shared compute loop bounded by attention + real
  events, not viewer count); multi-hazard models (wildfire · flood · earthquake · cyclone);
  a tile server + `/terminal` global console; a durable persistence layer with queryable
  belief history, bounded retention/roll-up, and scrubbable playback; a **planet-scale
  stress test** (`make global-stress`) with honest [scale ceilings](docs/scale_limits.md);
  and a **validated single-node deployment** stack ([deployment](docs/deployment.md)).
  Session 40 also fenced the **V1 California Case Study** off from the global system with
  clear in-app + README labeling. **320 backend tests green** (+1 network-gated skip),
  frontend 26 tests green.
  > ⚠️ **Uncalibrated-models caveat (still true, kept prominent):** no hazard model in this
  > repo has ever been fitted to real historical labels. The calibration/validation
  > pipeline is built and tested end-to-end but never ran against real fire history in this
  > environment, so **every deployed coefficient is an honestly-marked illustrative prior.**
  > VECTIS's scale and machinery are real; its hazard *numbers* are not yet validated
  > against ground truth. See [`docs/calibration_report.md`](docs/calibration_report.md).

- **Post-release consolidation (Sessions 41–42):** Session 41 added closed-form **driver
  attribution** to every hazard model (surfaced as the terminal's "Why" card for promoted
  cells) and per-feed **LIVE/SYNTHETIC transparency** throughout the terminal. Session 42
  retired the redundant V2 "Decision Intelligence" dashboard, V3 "Live Intelligence"
  console, and Maps pages (routes, components, and their backend endpoints — the Global
  Terminal is the single primary experience), moved the V1 Case Study into the collapsed
  **Origin Demo · V1 Archive** sidebar section, and fixed terminal UI bugs (brief-panel
  scrolling, map compass/north-reset, badge consistency).

**Full engineering history: [`HANDOFF.md`](HANDOFF.md)**.

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md) and [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md).
Security policy: [`SECURITY.md`](SECURITY.md).

## License

[Apache-2.0](LICENSE).
