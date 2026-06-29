# Frontend — VECTIS Decision Intelligence Console

The frontend is an **enterprise operational-intelligence console** (information-dense,
dark, keyboard-friendly) for the climate-risk vertical. It consumes the
real VECTIS backend API and is structured so new verticals and views slot in without
rework.

Stack: **React 18 + TypeScript + Vite + Tailwind + React Router + TanStack Query + Zustand**,
with **MapLibre GL** for maps and **Recharts** for charts.

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173 — dev server proxies /api and /health → :8000
npm run build      # tsc -b && vite build → dist/
npm run lint       # eslint, --max-warnings 0
npm run typecheck  # tsc --noEmit
npm run test       # vitest (jsdom + MSW)
```

No backend running? The UI still loads; data panels show their loading/error states. To see
real data, run the backend (`make api`) — the dev server proxies to it.

---

## Library choices (and why)

| Concern | Choice | Why |
|---|---|---|
| Build/dev | **Vite** | Fast HMR, native ESM, first-class TS; already the S1 toolchain. |
| Styling | **Tailwind CSS** | Utility-first keeps the dense, consistent enterprise look in markup; no CSS sprawl. Design tokens live in `tailwind.config.js`. |
| Routing | **React Router 6** | Standard nested-layout routing; the app shell is one layout route with page children. |
| Server state | **TanStack Query** | Caching, loading/error, refetch, and invalidation for API data — the single boundary between React and the backend. Pages never call `fetch`. |
| Client state | **Zustand** | Tiny, no boilerplate, no context wrappers. Holds only genuine UI state (current selection, sidebar). |
| Maps | **MapLibre GL** | Open-source (no token, no per-load billing), vector tiles, GPU-rendered, data-driven styling for choropleth risk layers. See *Map technology* below. |
| Charts | **Recharts** | Declarative SVG charts (SHAP driver bars, scenario deltas); good defaults, themable, carried over from S1. |
| Tests | **Vitest + Testing Library + MSW** | Vitest shares Vite config; MSW mocks the API at the network layer so page tests exercise the real query/hook path. |

### Map technology — why MapLibre over Mapbox/Leaflet/OpenLayers

- **Mapbox GL** is the closest peer but requires an access token and bills per map load —
  unacceptable for an open-source platform meant to run offline/self-hosted. MapLibre is the
  community fork of Mapbox GL v1 with the same API, no token, no billing.
- **Leaflet** is raster/DOM-first; smooth GPU vector rendering and data-driven choropleth
  styling (what risk layers need) are add-ons, not the core.
- **OpenLayers** is powerful but heavier API for what we need today.

**Scalability:** MapLibre renders vector tiles on the GPU, so the grid can grow from 240 cells
to thousands without DOM thrash. Risk layers are driven by feature properties (data-driven
paint), so adding layers (FIRMS detections, weather, NDVI) is a style/source change, not a
rewrite. Self-hostable tiles keep the offline-by-default guarantee.

---

## Architecture

```
frontend/src/
  app/         App (routes) · AppLayout (shell) · providers (QueryClient, Router)
  components/
    ui/        design system: Button, Card, Badge, Table, Modal, StatCard,
               states (Loading/Error/Empty), risk (RiskBadge)  — index.ts barrel
    layout/    Sidebar, Navbar, Page (header/container), nav config, icons
    map/       RiskMap (MapLibre choropleth), RiskLegend
    charts/    DriversChart (Recharts SHAP bars)
  features/    cross-cutting vertical UI, composed from components/
    risk/      RegionSelector, RiskDetailPanel
    reports/   ReportViewer, AgentTraceList
    simulations/ ScenarioPanel
  pages/       one component per route (Overview, RiskIntelligence, Maps,
               Reports, ReportDetail, Simulations, Datasets, NotFound)
  hooks/       queries.ts — all TanStack Query hooks (useAnalyses, useRunAnalysis, …)
  services/    API clients (apiClient, analyses, catalog, datasets) + queryKeys
    mocks/     clearly-labeled mock data for endpoints that don't exist yet
  stores/      Zustand: selectionStore (region/analysis/cell), uiStore (sidebar)
  types/       api.ts — TS mirror of backend schemas (DecisionReport, etc.)
  utils/       cn, format, risk (band/color helpers)
  styles/      index.css (Tailwind layers + tokens)
  test/        renderWithProviders, MSW server, fixtures, maplibre stub
```

**The dependency direction is one-way:** `pages → features → components → ui`. Pages own
routing and data (via hooks); features compose components into vertical UI; `components/ui` is
the dumb, reusable design system. State and network live behind `hooks/` and `services/`, so a
page is mostly layout.

### Data flow

```
page → hook (TanStack Query) → service client → apiClient.http → backend
                                                      ↑
                          stores/ (Zustand) hold selection/UI, not server data
```

- **`services/apiClient.ts`** is the only place that calls `fetch`. It reads
  `VITE_API_BASE_URL` (empty in dev → the Vite proxy handles `/api` and `/health`), and
  normalizes both backend error shapes (`{error:{code,message}}` and FastAPI `{detail}`) into
  a single `ApiError`.
- **`hooks/queries.ts`** is the single React↔backend boundary. `useRunAnalysis` is a mutation
  that, on success, seeds the report into the cache, invalidates the list, and focuses the new
  analysis in the selection store — so the UI updates without a manual refetch.
- **`stores/`** hold only UI state. `selectionStore` is the shared "what is the user looking
  at" (region, analysis id, selected cell); pages and panels read/write it instead of prop
  drilling.

### Routing & layout

`app/App.tsx` defines routes under a single `AppLayout` (persistent Sidebar + Navbar, scrollable
content outlet). Sidebar items: **Overview · Risk Intelligence · Maps · Reports · Simulations ·
Datasets** (config in `components/layout/nav.ts`). Unknown routes → `NotFoundPage`.

---

## Pages

| Route | Page | What it shows |
|---|---|---|
| `/` | **Overview** | Risk posture stat cards (count, avg, highest, system status) + recent-analyses table, live from `/api/v1/analyses` and `/health`. |
| `/risk` | **Risk Intelligence** | The vertical: region selector → **Run analysis** → interactive risk map + **Risk Detail Panel** (score, confidence, drivers, recommended actions) + SHAP **DriversChart**. |
| `/maps` | **Maps** | Full-bleed MapLibre risk map with legend. |
| `/reports` | **Reports** | List of decision reports. |
| `/reports/:id` | **Report Detail** | **ReportViewer** — executive summary, technical explanation, evidence, confidence, recommendations, with explicit separation of *AI insight* vs *supporting evidence* vs *human decision*; plus the agent trace. |
| `/simulations` | **Simulations** | **ScenarioPanel** — real what-if results read from the report's Simulation trace, plus an architecture-only custom-scenario builder (controls wired, disabled pending backend). |
| `/datasets` | **Datasets** | Catalog of data connectors (bundled sample = active; FIRMS/ERA5/Copernicus = planned). **Mock-backed** — see below. |

---

## Real data vs mocks (and how they're separated)

The frontend consumes **real backend endpoints** wherever they exist: `POST /api/v1/analyses`,
`GET /api/v1/analyses`, `GET /api/v1/analyses/{id}`, `GET /api/v1/regions`,
`GET /api/v1/models/{region}`, `GET /health`.

Where the backend has **no endpoint yet**, the mock is quarantined and loudly labeled:

- All mock data lives under **`services/mocks/`** with a `⚠️ MOCK DATA` header and a
  `*_ARE_MOCK = true` flag.
- The only current mock is the **Datasets catalog** (`services/mocks/datasets.ts`) — it
  describes connectors that genuinely exist in the backend, shaped as an async client so
  swapping in a real `/datasets` endpoint is a one-line change in `services/datasets.ts`.
- The **custom scenario builder** in `ScenarioPanel` is architecture-only: its controls are
  visibly disabled (`Preview` badge) because the backend doesn't accept custom perturbation
  parameters yet. The *displayed* scenarios are real, read from the report trace.

No hardcoded production data anywhere else.

---

## Environment configuration

| Var | Where | Meaning |
|---|---|---|
| `VITE_API_BASE_URL` | build time | API origin baked into the bundle (browser calls the API directly). Empty in dev → Vite proxies `/api` and `/health` to `:8000`. The Docker frontend image bakes it via an `ARG`. |

---

## Testing

`npm run test` runs Vitest in jsdom with **MSW** mocking the API at the network layer (so
hooks/services run for real). Coverage:

- **Component test** — `Button` (variants, disabled, click).
- **Feature test** — `ReportViewer` (renders summary/evidence/recommendations).
- **Page + API-mock tests** — `OverviewPage` (fetches and renders recent analyses) and
  `RiskIntelligencePage` (run-analysis flow end-to-end against mocked POST+GET).

MapLibre needs WebGL (absent in jsdom), so the bare `maplibre-gl` module is aliased to a stub
in the test env only (`src/test/maplibreStub.ts`) — the CSS subpath import still resolves.

---

## Conventions

- Import via the `@/` alias (→ `src/`).
- A page never calls `fetch` — it uses a hook from `hooks/queries.ts`.
- Reusable visuals go in `components/ui` and are exported from its `index.ts` barrel.
- Risk band → color/label logic lives once in `utils/risk.ts`; don't re-derive it inline.
- New mock? Put it in `services/mocks/`, label it, and flag it — never inline a mock in a page.
