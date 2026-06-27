<div align="center">

# ▲ VECTIS

**Autonomous Intelligence System for Decision Analysis**

*An open-source AI decision-intelligence platform that turns complex real-world data
into explainable, actionable intelligence.*

[![CI](https://github.com/your-org/vectis/actions/workflows/ci.yml/badge.svg)](.github/workflows/ci.yml)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](backend/pyproject.toml)

</div>

---

## What VECTIS is

VECTIS answers four questions about a complex real-world problem:

> **What is happening? · Why is it happening? · What could happen next? · What should we do?**

It combines a reproducible **data pipeline**, a **multi-agent AI system**, **machine
learning with built-in explainability (SHAP)**, lightweight **simulation**, and an
**enterprise console** — and it never asks you to trust a black box. Every score is
attributed to its drivers, every claim is backed by evidence, and a mandatory
**Critic agent** challenges the analysis before it reaches you. A human stays in control.

The first complete vertical is **Climate Risk Intelligence** — wildfire risk — demoed
end-to-end on **Lombardy, Italy**.

### Example output — a Decision Intelligence Report

```
Area:        Lombardy, Italy
Risk Score:  77/100  (SEVERE)
Confidence:  89%
Main Drivers:  drought conditions · vegetation stress · historical fire activity · terrain slope
Scenario:    "hotter, drier month" → 89/100 (+12)
Recommended: increase monitoring · pre-position resources · investigate anomalies
Critic:      APPROVED — all driver claims backed by evidence
```

It runs **fully offline** with a deterministic mock LLM and a bundled sample dataset —
no API keys required.

---

## Architecture

```
        React + TS console (MapLibre map · SHAP drivers · AI report)
                              │  /api/v1
                              ▼
                     FastAPI  +  AnalysisService
                              │
                   Agent Orchestrator (typed DAG)
        Discovery → Analyst → ML Research → Simulation → Report ⟲ Critic
                              │
        ┌─────────────────────┴─────────────────────┐
        ▼                                            ▼
  Data pipeline                               ML + explainability
  ingest→validate→clean→feature-engineer      LogReg/RF/XGBoost · SHAP · model cards
        │                                            │
   Connectors (sample / FIRMS·ERA5·Copernicus)  Model registry (disk)
        │
   PostgreSQL + PostGIS        LLM: Claude | Mock (env-selected)
```

Full detail: [`docs/architecture.md`](docs/architecture.md).

| Layer | Stack |
|---|---|
| Backend | Python 3.11, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic |
| Data | pandas, content-hashed pipeline, PostGIS |
| ML | scikit-learn, XGBoost, **SHAP** |
| Agents | typed orchestrator + Critic loop, **two engines (custom / LangGraph)**; Anthropic Claude or mock |
| Frontend | React 18, TypeScript, MapLibre GL, Recharts |
| Infra | Docker Compose, GitHub Actions CI, ruff + mypy + pytest |

> **Architecture diagram:** the ASCII overview above is the canonical diagram; a rendered
> version belongs under `docs/assets/` (placeholder — see `docs/architecture.md`).

### Repository structure

```
VECTIS/
├── backend/                 # FastAPI service, agents, ML, data pipeline
│   ├── vectis/
│   │   ├── api/             # FastAPI app + routers (analyses, regions, models, health)
│   │   ├── agents/          # orchestrator + 6 agents + LLM clients (two engines)
│   │   ├── core/            # config, logging, exceptions, schemas (the contracts spine)
│   │   ├── data/            # regions, connectors (sample + live stubs), pipeline
│   │   ├── models/          # training, evaluation, SHAP explain, registry, predictor
│   │   ├── database/        # SQLAlchemy models, session, repository
│   │   ├── services/        # AnalysisService (orchestration entry point)
│   │   └── scripts/         # generate_sample, train, demo
│   ├── alembic/             # database migrations
│   └── tests/               # unit · model · integration · api  (pytest)
├── frontend/                # React + TS decision-intelligence console
│   └── src/                 # app · pages · features · components · hooks · services · stores
├── docs/                    # architecture · agents · ml_pipeline · data_pipeline · frontend · development
├── data/                    # bundled sample + staging dirs (raw/processed/…)
├── .github/                 # CI workflow, issue/PR templates
├── docker-compose.yml       # db (PostGIS) + backend + frontend
└── HANDOFF.md               # cross-session engineering source of truth
```

---

## Intelligence layer (AI agents + ML)

VECTIS threads a typed `AgentState` through six agents — **Discovery → Analyst →
ML Research → Simulation → Report ⟲ Critic** — to produce an explainable,
human-in-the-loop Decision Report. Highlights:

- **Two interchangeable orchestration engines** behind one interface, selected by
  `VECTIS_ORCHESTRATOR`: a default **`custom`** typed DAG (deterministic, dependency-light)
  and an optional **`langgraph`** `StateGraph`. Both run the same agents and produce
  identical reports (parity-tested). → [`docs/agents.md`](docs/agents.md)
- **Mandatory Critic** — a deterministic gate that blocks any claim not backed by
  evidence and can trigger a bounded revision loop. No report bypasses it.
- **ML with built-in explainability** — LogReg/RF/XGBoost are compared and selected by
  discrimination + calibration; every prediction carries **SHAP** drivers, so it always
  answers *"why did the model decide this?"*. → [`docs/ml_pipeline.md`](docs/ml_pipeline.md)
- **LLM narrates, never decides** — agents compute structured, evidence-backed results;
  the LLM only phrases them, with a deterministic offline fallback.

---

## Quick start

### Option A — Docker (full stack)

```bash
cp .env.example .env
make up          # db (PostGIS) + backend + frontend
# Backend: http://localhost:8000/docs   Frontend: http://localhost:5173
```

The backend applies migrations (`alembic upgrade head`), seeds the sample dataset, and
trains a model on first start. Probes: `GET /health` (liveness),
`GET /health/ready` (database connectivity).

### Option B — Local backend (no Docker, no API key)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

python -m vectis.scripts.demo        # run one analysis, print the Decision Report
make api                            # or serve the API at :8000
```

Then in another shell:

```bash
curl -X POST localhost:8000/api/v1/analyses -H "Content-Type: application/json" \
     -d '{"region":"liguria"}'
```

### Frontend dev server

```bash
cd frontend && npm install && npm run dev   # http://localhost:5173 (proxies /api → :8000)
```

---

## Frontend — Decision Intelligence Console

An **enterprise operational-intelligence console** (Palantir-style: dense, dark, fast) that
consumes the real backend API. Stack: **React 18 + TypeScript + Vite + Tailwind + React Router
+ TanStack Query + Zustand**, with **MapLibre GL** (open-source vector maps, no token/billing)
for the risk map and **Recharts** for SHAP/driver charts.

Pages (sidebar): **Overview · Risk Intelligence · Maps · Reports · Simulations · Datasets**.
The Risk Intelligence view runs an analysis and renders an interactive risk map, a risk-detail
panel (score, confidence, drivers, recommended actions), and the AI Decision Report with
explicit separation of *AI insight* vs *supporting evidence* vs *human decision*. Server state
goes through TanStack Query hooks; the only mock-backed view is the Datasets catalog (clearly
labeled under `services/mocks/`, pending a backend endpoint).

```bash
cd frontend
npm run build   # tsc -b && vite build
npm run lint    # eslint, 0 warnings
npm run test    # vitest + Testing Library + MSW
```

> **Screenshots:** _placeholder_ — add console captures (Overview, Risk Intelligence map,
> Report viewer) under `docs/assets/` and link them here.

Full architecture, library rationale, and the real-vs-mock policy: [`docs/frontend.md`](docs/frontend.md).

---

## Example analysis (what happens under the hood)

1. **Discovery** acquires the Liguria grid (240 cells) from the sample connector.
2. **Analyst** runs the pipeline and surfaces signals ("62% of cells show elevated drought").
3. **ML Research** scores each cell and attributes the score to drivers via SHAP.
4. **Simulation** perturbs climate drivers ("hotter, drier month") and re-scores.
5. **Report** composes a Decision Report — score, drivers, evidence, recommended actions.
6. **Critic** verifies every driver is backed by evidence and the actions match the risk;
   it can send the report back for a bounded revision.

---

## Extending VECTIS

- **Add an agent** → [`docs/agents.md`](docs/agents.md)
- **Add a dataset / live connector** → [`docs/data_pipeline.md`](docs/data_pipeline.md)
- **Frontend architecture & conventions** → [`docs/frontend.md`](docs/frontend.md)
- **Dev workflow, testing, conventions** → [`docs/development.md`](docs/development.md)

Use a real LLM by setting `VECTIS_LLM_PROVIDER=claude` and `VECTIS_ANTHROPIC_API_KEY`
(install extras: `pip install -e '.[llm]'`). The LLM only *narrates* already-computed,
evidence-backed findings — it never invents numbers — so outputs stay explainable.

---

## Project status & roadmap

VECTIS v1.0 (Session 1) delivers the foundation **and a complete working vertical slice**.
See [`HANDOFF.md`](HANDOFF.md) for engineering history and next steps. Highlights on the
roadmap: live Earth-observation connectors (NASA FIRMS / ERA5 / Copernicus), a knowledge-graph
layer, additional regions, authentication, and LLM-assisted (not LLM-decided) critique.

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md) and our [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md).
Security policy: [`SECURITY.md`](SECURITY.md).

## License

[Apache-2.0](LICENSE).
