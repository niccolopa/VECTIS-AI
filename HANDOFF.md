# HANDOFF — VECTIS

> Source of truth for cross-session continuity. A new engineer (or a fresh Claude
> Code session with zero context) should be able to continue from this file alone.
> **Read this first. Update it after every major milestone.**

Last updated: **2026-06-27** · End of **Session 5** (+ post-S5 maintenance: tsconfig `baseUrl`
deprecation fix).

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

Build **VECTIS** (Autonomous Intelligence System for Decision Analysis): a production-grade,
open-source **AI decision-intelligence platform** that turns complex real-world data into
**explainable, actionable** intelligence, answering: *what is happening · why · what could
happen next · what to do.*

Non-negotiables: explainable AI, human-in-the-loop, modular architecture, reproducibility,
clean engineering, exceptional docs. First vertical: **Climate (wildfire) Risk Intelligence**,
demoed on **Liguria, Italy**.

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

## What Worked (decisions that succeeded — keep these)

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

---

## Next Steps (Session 6 — pick up here)

**Done so far (do not redo):** S1 vertical slice; S2 DB session layer + migrations + readiness;
S3 LangGraph engine + two-engine interface + extended ML metrics + auditable model selection;
S4 the full enterprise frontend console; **S5 OSS/production-readiness hardening** (frontend
tests in CI, Docker healthchecks + reproducible `npm ci`, `.editorconfig`, repo-structure docs,
security review). Note: the **NASA FIRMS / live-data work was never done** — it remains the top
backend priority.

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
6. **Frontend polish:** route-level code-splitting / `manualChunks` (bundle ~1.4 MB), an
   orchestration-engine indicator, evidence drill-down, and console screenshots into `docs/assets/`
   (README has the placeholder).
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
pytest                             # 48 tests, all green

# Frontend
cd frontend && npm install && npm run dev    # http://localhost:5173 (proxies /api → :8000)
npm run lint && npm run typecheck && npm run test && npm run build   # all green; 7 tests
```
Backend spine, read in order: `core/schemas.py` → `agents/runtime.py` → `agents/orchestrator.py`
(+ `agents/langgraph_engine.py`) → `agents/critic.py` → `models/predictor.py`. To switch engine:
`VECTIS_ORCHESTRATOR=langgraph`. Frontend spine: `app/App.tsx` → `hooks/queries.ts` →
`services/apiClient.ts` → `pages/RiskIntelligencePage.tsx`. Full frontend docs: `docs/frontend.md`.
