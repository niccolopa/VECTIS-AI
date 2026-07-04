# Development Guide

## Prerequisites

- Python 3.11+
- Node 20+
- (optional) Docker + Docker Compose for the full stack
- (optional) PostgreSQL/PostGIS — not required for dev/test (in-memory fallback)

## Setup

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# Frontend
cd ../frontend
npm install
```

## Common tasks (Makefile)

| Command | Does |
|---|---|
| `make migrate` | Apply database migrations (`alembic upgrade head`) |
| `make revision m="msg"` | Autogenerate a new migration from model changes |
| `make seed` | Generate the deterministic California sample |
| `make train` | Train baselines, select best, write model card |
| `make demo` | Run one analysis end-to-end, print the Decision Report |
| `make api` | Serve the API at :8000 (`/docs` for OpenAPI) |
| `make test` | Run the backend test suite |
| `make lint` | ruff + mypy (backend) and eslint (frontend) |
| `make up` / `make down` | Start / stop the full Docker stack |

## Configuration

All config is environment-driven via `VECTIS_`-prefixed variables, centralized in
`backend/vectis/core/config.py` (Pydantic `Settings`). Copy `.env.example` → `.env`.
Nothing else reads `os.environ` directly. Key knobs:

- `VECTIS_LLM_PROVIDER` — `mock` (default, offline) or `claude`.
- `VECTIS_DATABASE_URL` — Postgres in Docker; tests force a temp SQLite file.
- `VECTIS_CRITIC_MAX_REVISIONS` — bound on the Report⟲Critic loop.

## Database & migrations

The engine/session layer is a single shared source in
`backend/vectis/database/session.py`: `get_engine()` / `get_sessionmaker()` (cached,
lazy), the `get_db()` FastAPI dependency, `init_db()`, and `ping()`.

Schema is managed by **Alembic** (`backend/alembic/`). `alembic/env.py` reads the
database URL from VECTIS settings (not `alembic.ini`), so migrations always target
the same database as the app.

```bash
make migrate                       # alembic upgrade head
make revision m="add areas table"  # autogenerate from model changes, then review
```

`init_db()` (`create_all`) remains as a zero-config convenience for dev/test; in
Docker and production, `alembic upgrade head` runs first (see `docker-compose.yml`).

**Health probes:** `GET /health` is liveness; `GET /health/ready` verifies database
connectivity (200 ready / 503 degraded). The repository falls back to in-memory
storage when the DB is unreachable, so the demo path still works.

## Data staging

On-disk pipeline artifacts live under `data/` (`raw/ → validation/ → processed/`,
plus `pipelines/` manifests and `schemas/` snapshots). Only `samples/` and `schemas/`
are tracked; the rest are generated (see [`../data/README.md`](../data/README.md)).

## Testing

```bash
cd backend && pytest                 # all
pytest -m model                      # ML metric-threshold tests
pytest -m integration                # orchestrator end-to-end
```

The suite (`backend/tests/`) is layered: `unit/` (schemas, pipeline, sample), `model/`
(training thresholds + SHAP), `integration/` (orchestrator), `api/` (endpoints). A
session fixture seeds data and trains a model into a temp dir, so tests are
self-contained and deterministic (LLM forced to `mock`).

## Code standards

- **Backend**: fully type-hinted; `ruff` + `mypy` must pass. Logging via
  `get_logger(__name__)` (structlog) — no bare `print` in library code.
- **Frontend**: strict TypeScript; `eslint` clean; `npm run build` must succeed.
- **Contracts first**: changes to `DecisionReport`/`AgentState` are reviewed carefully.

CI (`.github/workflows/ci.yml`) runs lint + type-check + tests for both backend and
frontend on every push/PR.

## Repository layout

```
backend/vectis/
  api/        FastAPI app, routers, deps
  agents/     base, orchestrator, the 6 agents, llm/ providers
  core/       config, logging, exceptions, schemas (the contracts)
  data/       regions, connectors/, pipeline/
  models/     training, evaluation, explain (SHAP), registry, predictor
  services/   analysis_service (API ↔ agents seam)
  database/   SQLAlchemy models, repository
  scripts/    generate_sample, train, demo
frontend/src/ App, lib/api, components/ (MapView, DriversChart, ReportPanel)
```

## Troubleshooting

- **`ModelNotTrainedError`** → run `make seed && make train`.
- **Sample missing** → `make seed`.
- **Frontend can't reach API** → ensure the backend is on :8000 (dev server proxies
  `/api`), or set `VITE_API_BASE_URL`.
- **XGBoost import error in Docker** → the backend image installs `libgomp1`; rebuild.
