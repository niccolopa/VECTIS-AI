<div align="center">

# ▲ VECTIS

**Real-Time Probabilistic Decision Intelligence Platform**

*Open-source. Turns a live stream of real-world observations into explainable
**distributions over possible futures** — not single-number guesses — and narrates
them with an auditable AI board whose numbers are produced entirely by deterministic math.*

[![CI](https://github.com/your-org/vectis/actions/workflows/ci.yml/badge.svg)](.github/workflows/ci.yml)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](backend/pyproject.toml)
[![Backend tests](https://img.shields.io/badge/backend%20tests-107%20passing-brightgreen.svg)](backend/tests)
[![Scale](https://img.shields.io/badge/Monte%20Carlo-1M%20scenarios%20in%20~0.8s-00ffd5.svg)](docs/v2_simulation_engine.md)

</div>

---

## What VECTIS is

Most "AI risk" tools hand you one number and ask you to trust it. VECTIS refuses to.
It simulates **thousands to millions of possible futures**, weights them by a
continuously-updated belief, and shows you the full distribution — then lets an AI
analyst board explain it *without ever touching the math*.

VECTIS is built in two layers:

- **V1 — Reactive Decision Intelligence.** Answers *what is happening · why · what
  could happen next · what to do*, via a data pipeline, ML with **SHAP**
  explainability, and a multi-agent system with a mandatory **Critic**.
- **V2 — The Simulation & Forecasting Engine.** Answers a harder question: *given the
  current state of the world, what are all plausible futures, and with what
  probability?* It produces **distributions over outcomes** via Monte Carlo, updates
  them in real time with **Bayesian inference**, and runs a **digital twin** of the
  region you care about.

The first complete vertical is **Climate (wildfire) Risk Intelligence**, demoed
end-to-end on **Liguria, Italy**. It runs **fully offline** with a deterministic mock
LLM and a bundled dataset — **no API keys required**.

---

## The engineering that makes it serious

| Capability | What it means | Where |
|---|---|---|
| **Vectorized Monte Carlo** | 100k–1M scenarios per run in pure NumPy/SciPy, reproducible per `(seed, n_workers)` | [`simulation/engine/runner.py`](backend/vectis/simulation/engine/runner.py) |
| **Bayesian belief update** | Each observation shifts a posterior over scenarios in log-space (exact, not heuristic) | [`simulation/probability/bayesian.py`](backend/vectis/simulation/probability/bayesian.py) |
| **Digital twin** | A self-updating `RegionTwin` holds state + belief and re-runs only when beliefs move materially | [`digital_twin/`](backend/vectis/digital_twin/) |
| **Real-time stream** | `POST /stream/ingest` returns **202 immediately**; CPU-bound math runs off the event loop; results pushed over WebSocket | [`streaming/`](backend/vectis/streaming/) |
| **The Math Firewall** | LLMs **never** compute. Every number on a report is copied from the engine; the AI writes only prose | [`agents/board/`](backend/vectis/agents/board/) |
| **TTL + LRU caching** | Identical re-runs return in microseconds (~6000× faster) | [`simulation/caching.py`](backend/vectis/simulation/caching.py) |
| **Distributed-ready** | A Ray/Dask abstraction (override *dispatch* only) with a runnable local stub — zero heavy deps | [`simulation/engine/distributed.py`](backend/vectis/simulation/engine/distributed.py) |

> **The Golden Rule of V2:** all probabilistic computation lives in deterministic
> libraries behind explicit interfaces. Nothing under `simulation/` imports the agents
> layer. LLMs re-enter only as *Analyst* agents that *read* the numbers. The
> "LLM-narrates-not-decides" discipline is enforced at the type boundary.

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
            React Dashboard ◄── LangGraph Analyst Board
       (Scenario Explorer · Probability Timeline ·   (Analyst→Scenario→
        What-If Simulator · AI Brief)                 Debate→Red-Team)
```
<sub>*FIRMS active-fire ingestion is on the V3 roadmap.</sub>

| Layer | Stack |
|---|---|
| Simulation | **NumPy · SciPy** (vectorized Monte Carlo, Bayesian inference) |
| Backend | Python 3.11, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, structlog |
| Agents | LangGraph board + custom DAG (two engines); Anthropic Claude or deterministic mock |
| ML (V1) | scikit-learn, XGBoost, **SHAP** |
| Frontend | React 18, TypeScript, Vite, Tailwind, TanStack Query, **Recharts**, MapLibre GL |
| Infra | Docker Compose, GitHub Actions CI, ruff + mypy + pytest |

---

## Quick start

### Option A — the offline demos (no Docker, no API key)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

python -m vectis.scripts.demo_v2     # V2: full simulation pipeline as a tactical console
make stress                          # 1,000,000-scenario Monte Carlo + honest verdict
python -m vectis.scripts.demo        # V1: one reactive Decision Report
```

### Option B — the live dashboard

```bash
# terminal 1 — backend API at :8000
cd backend && make api

# terminal 2 — frontend at :5173
cd frontend && npm install && npm run dev
```

Open <http://localhost:5173> and click **Decision Intelligence** in the sidebar for the
V2 dashboard. Push a live observation and watch the Probability Timeline move:

```bash
curl -s -X POST localhost:8000/api/v1/stream/ingest -H "Content-Type: application/json" \
  -d '{"kind":"weather_alert","source":"demo","region":"liguria","variable":"temp_anomaly_c","value":4.0,"severity":"critical"}'
```

### Option C — Docker (full stack)

```bash
cp .env.example .env
make up          # db (PostGIS) + backend + frontend
```

> Use a real LLM by setting `VECTIS_LLM_PROVIDER=claude` and `VECTIS_ANTHROPIC_API_KEY`
> (`pip install -e '.[llm]'`). The LLM only *narrates* already-computed numbers.

---

## The V2 Dashboard

A dark, dense, enterprise-grade tactical console that consumes the real engine:

- **Scenario Explorer** — each branch (Baseline · Hotter & Drier · Extreme Wind) as a
  **box-and-whisker** over its full outcome distribution (p05/p50/p95), not a single number.
- **Probability Timeline** — risk × confidence over time, fed live by the WebSocket stream.
- **What-If Simulator** — drag temperature/humidity/vegetation/fire-history and re-run the
  Monte Carlo **synchronously** (cache-served), with the delta vs. current risk.
- **AI Intelligence Brief** — the LangGraph board's report: analyst summary, scenario
  storylines, an optimist/pessimist debate, and a red-team critique.

A maintainer's 2-minute showcase script: [`docs/demo_video_script.md`](docs/demo_video_script.md).

---

## Roadmap → V3

V2 makes VECTIS a real-time probabilistic engine for **one** twin. V3 turns it into a
**living, multi-domain intelligence network**:

- **Live data streams.** NASA **FIRMS** active-fire ingestion (then ERA5/Copernicus),
  delivered over **Apache Kafka** so the digital twin reacts to the real world, not
  synthetic events.
- **Persistence & history.** ORM-backed twin + belief-trajectory storage, so risk
  history is queryable and auditable across restarts.
- **Reinforcement learning for suggested actions.** Move beyond *describing* risk to
  *recommending* interventions (where to pre-position resources) and learning from outcomes.
- **Multi-twin interaction.** Twins that influence each other across domains —
  e.g. **Climate × Finance** (wildfire risk → insurance/commodity exposure) — composed
  through the existing `StateManager`.
- **Horizontal scale.** Promote the distributed stub to real **Ray/Dask** clusters and
  move `StateManager`/broadcaster/cache to Redis for many regions concurrently.

Full engineering history and next steps: **[`HANDOFF.md`](HANDOFF.md)**.

---

## Project status

- **V1 (Sessions 1–6):** complete reactive vertical — pipeline, ML+SHAP, agents, console.
- **V2 (Sessions 6–15):** complete — Monte Carlo engine, Bayesian update, real-time
  streaming, digital twin, LangGraph board, 1M-scenario scale, and the dashboard. **107
  backend tests green.**

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md) and [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md).
Security policy: [`SECURITY.md`](SECURITY.md).

## License

[Apache-2.0](LICENSE).
