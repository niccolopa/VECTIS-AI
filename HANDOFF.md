# HANDOFF — VECTIS

> Source of truth for cross-session continuity. A new engineer (or a fresh Claude
> Code session with zero context) should be able to continue from this file alone.
> **Read this first. Update it after every major milestone.**

Last updated: **2026-06-27** · End of **Session 9** (V2 Real-Time Intelligence Layer —
`streaming/` ingest → Bayesian update → conditional MC re-run → WebSocket broadcast; 73 backend
tests green).

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

Build **VECTIS**: a production-grade, open-source **AI decision-intelligence platform** that
turns complex real-world data into **explainable, actionable** intelligence. First vertical:
**Climate (wildfire) Risk Intelligence**, demoed on **Liguria, Italy**.

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
**7 Vitest tests pass** (4 files), `vite build` succeeds. Multi-page SPA, Palantir-style dense
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

Focus: **frontend visual redesign — "Matrix meets Palantir Gotham 3D" tactical aesthetic.**
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
> *Session 6* for the Matrix/Gotham frontend redesign (it matches the latest commit). To keep the
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

**Quality bar ("would a Palantir senior approve this for a high-frequency sim engine?"):** the math
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

## What Worked (decisions that succeeded — keep these)

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

## Next Steps (Session 10 — pick up here)

**Done so far (do not redo):** S1 vertical slice; S2 DB session layer + migrations + readiness;
S3 LangGraph engine + two-engine interface + extended ML metrics + auditable model selection;
S4 the full enterprise frontend console; **S5 OSS/production-readiness hardening** (frontend
tests in CI, Docker healthchecks + reproducible `npm ci`, `.editorconfig`, repo-structure docs,
security review); **S6 the "Matrix x Palantir Gotham" tactical redesign**; **V2 Foundation**
(the `simulation/` skeleton — schemas + ABC interfaces + docs); **S7 the Monte Carlo engine**
(`distributions`/`sampler`/`runner`/`models/wildfire`/`scenarios/generator` — vectorized, seeded,
reproducible, optional process-pool parallelism; 100k in ~70 ms; 8 tests); **S8 the Bayesian
update + Confidence Score** (`probability/bayesian` `GaussianBayesianUpdater`, `probability/
uncertainty`, `probability/calibration` blueprint; discrete exact-evidence Bayes in log-space;
10 tests); **S9 the Real-Time Intelligence Layer** (`streaming/` package: `events`/`updater`/
`broadcaster` + `api/routers/stream.py`; 202-ingest → BackgroundTask → debounce → Bayesian update
→ conditional MC re-run → WebSocket broadcast; 7 tests). Note: the **NASA FIRMS / live-data work
was never done** — it remains a top backend priority and feeds both V2 State Estimation *and* the
S9 streaming layer (which currently ingests synthetic events). The **`states/base.py`
`StateEstimator` and `forecasting/Forecast` impls are still ABC-only** — deferred again below.

### Session 10 PRIMARY: Digital Twin Foundation

The streaming layer can now react to events, but it reacts on a **hand-set** Liguria twin
(`liguria_wildfire_state()`) and **synthetic** events. Session 10 should make the digital twin
*real and persistent* — still **deterministic libraries only, no LLMs in the math**:

- **`states/base.py` impl → `SampleStateEstimator`.** Build a `WorldState` (per-variable
  uncertainty) from the V1 feature pipeline (`data/pipeline/`) instead of the hand-set factory, so
  the twin reflects estimated reality. Wire it into `build_default_updater()` so streaming starts
  from an estimated state. (Carried from S8/S9.)
- **Live observation source → the S9 streaming loop.** Replace synthetic ingest with a real feed:
  **NASA FIRMS** active-fire detections (then ERA5 weather) mapped into `SensorReading`/
  `WeatherAlert` events. The streaming plumbing already exists — this is a connector + a poller
  that POSTs to `/stream/ingest` (or calls `updater.process` directly). Keep offline the default.
- **Persist the twin + belief history.** The `RealTimeUpdater` state is in-memory only (lost on
  restart). Add an ORM-backed store for `WorldState` snapshots + the posterior `ScenarioSet` over
  time, so the twin survives restarts and the belief trajectory is queryable/auditable.
- **`forecasting/` impl → public `Forecast`.** Adapt a `SimulationRun` into a `Forecast` (mixture
  over scenarios weighted by **posterior** priors → single horizon distribution + per-band
  probabilities; reuse `posterior_mixture_risk` + `scenario_confidence`) + an API endpoint. Then
  the V1 **Analyst** agent that *reads* and narrates it (never recomputes). (Carried from S8.)
- **Calibration:** `WildfireHazardModel` coefficients are illustrative (`ponytail:` in
  `models/wildfire.py`); `probability/calibration.py` reliability-curve + recalibration are
  blueprint stubs. Once FIRMS labels exist, fit the hazard and log resolved forecasts into a
  `Calibrator` so `brier_score` becomes a tracked metric.
- **Streaming hardening (when scaling out):** the S9 layer is single-process/in-memory by design
  (global lock, in-memory debounce dict, in-process WebSocket fan-out). To scale: swap the
  broadcaster for Redis pub-sub, the debounce dict for a Redis TTL key, and BackgroundTasks for a
  Celery/Kafka worker — `RealTimeUpdater.process()` stays unchanged (that's the whole point).

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
pytest                             # 73 tests, all green

# Frontend
cd frontend && npm install && npm run dev    # http://localhost:5173 (proxies /api → :8000)
npm run lint && npm run typecheck && npm run test && npm run build   # all green; 7 tests
```
Backend spine, read in order: `core/schemas.py` → `agents/runtime.py` → `agents/orchestrator.py`
(+ `agents/langgraph_engine.py`) → `agents/critic.py` → `models/predictor.py`. To switch engine:
`VECTIS_ORCHESTRATOR=langgraph`. Frontend spine: `app/App.tsx` → `hooks/queries.ts` →
`services/apiClient.ts` → `pages/RiskIntelligencePage.tsx`. Full frontend docs: `docs/frontend.md`.
