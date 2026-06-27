# Architecture

VECTIS is a layered system. Each layer has one job and a typed contract with its
neighbors, so components are independently testable and replaceable.

```
┌─────────────────────────────────────────────────────────────────────┐
│ Frontend  — React + TS console (MapLibre map, SHAP chart, AI report) │
└───────────────────────────────┬─────────────────────────────────────┘
                                 │  HTTP /api/v1
┌───────────────────────────────▼─────────────────────────────────────┐
│ API  — FastAPI routers → AnalysisService → AnalysisRepository        │
│        (analyses · regions · models · health)                        │
└───────────────────────────────┬─────────────────────────────────────┘
                                 │
┌───────────────────────────────▼─────────────────────────────────────┐
│ Agents  — typed Orchestrator over a shared AgentState                │
│   Discovery → Analyst → ML Research → Simulation → Report ⟲ Critic    │
└───────────────┬───────────────────────────────┬─────────────────────┘
                │                               │
┌───────────────▼─────────────┐   ┌─────────────▼───────────────────────┐
│ Data pipeline               │   │ ML + explainability                 │
│ ingest→validate→clean→      │   │ training · evaluation · SHAP ·       │
│ feature-engineer (hashed)   │   │ registry (model cards) · predictor   │
└───────────────┬─────────────┘   └─────────────┬───────────────────────┘
                │                               │
┌───────────────▼─────────────┐   ┌─────────────▼───────────────────────┐
│ Connectors                  │   │ Model registry (disk artifacts)     │
│ sample (default) · live*    │   │                                     │
└─────────────────────────────┘   └─────────────────────────────────────┘
        PostgreSQL + PostGIS              LLM: Claude | Mock
```

## The contracts spine (`backend/vectis/core/schemas.py`)

Everything agrees on a small set of Pydantic models. Changing them is deliberate.

- **`DecisionReport`** — the deliverable. Risk score (0–100), confidence (0–1),
  drivers, evidence, recommended actions, per-cell risks (for the map), the Critic's
  review, the model-card reference, and the full agent trace.
- **`AgentState`** — the mutable state threaded through the orchestrator. Heavy,
  non-serializable artifacts (DataFrames, fitted models) live on a separate
  `RunContext` blackboard so the state stays serializable.
- **`Driver`** — a SHAP-attributed factor: signed `contribution` + `direction`.
- **`RegionPrediction` / `CellPrediction`** — ML outputs with attributions.

## Design principles

1. **Explainability is structural.** The model never produces a score without SHAP
   drivers; the report schema requires evidence; the Critic enforces it.
2. **Reproducible & offline by default.** Bundled sample data + deterministic mock LLM
   → `docker compose up` yields identical reports with no credentials.
3. **Human-in-the-loop.** VECTIS recommends; the Critic's verdict and full trace travel
   with every report so a person can audit the basis of any conclusion.
4. **Swappable internals.** Connectors, the LLM provider, the repository, and the
   orchestrator all sit behind interfaces (sample↔live, mock↔Claude, memory↔SQL,
   custom↔LangGraph).

## Request lifecycle

1. `POST /api/v1/analyses {region}` → `AnalysisService.run`.
2. The `Orchestrator` builds a `RunContext` (region, connector, registry) and an
   `AgentState`, then runs the agent DAG (see [`agents.md`](agents.md)).
3. The resulting `DecisionReport` is persisted via the repository (SQL if a database is
   reachable, else in-memory) and returned.
4. `GET /api/v1/analyses/{id}` re-fetches it.

## Persistence

The engine/session layer is a single shared source (`database/session.py`):
`get_engine()`/`get_sessionmaker()` (cached, lazy), the `get_db()` FastAPI dependency,
`init_db()`, and `ping()` (used by the `/health/ready` probe). `database/base.py` holds
only the declarative `Base`.

`SqlAnalysisRepository` stores denormalized headline metrics plus the full report JSON.
`build_repository()` verifies connectivity (`ping`) and ensures schema before choosing
the SQL path, otherwise falling back to `MemoryAnalysisRepository` so dev/test/demo never
require Postgres. PostGIS is the production target for geospatial-native storage.

Schema is versioned with **Alembic** (`backend/alembic/`); `env.py` reads the database
URL from VECTIS settings so migrations and the app always agree. Production runs
`alembic upgrade head` on startup.

\* Live connectors (FIRMS/ERA5/Copernicus) are stubs pending credentials — see
[`data_pipeline.md`](data_pipeline.md).
