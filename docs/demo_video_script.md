# VECTIS — Recorded Demo Script (V4 release)

A shot-by-shot storyboard for a recorded showcase. VECTIS ships **two architecturally
distinct** analysis systems in one console, and the single most important job of this
demo is to **never let a viewer confuse them**:

1. **Part 1 — the V4 Global Terminal.** The flagship: a **planet-scale**, live, tiered
   system over a worldwide H3 grid. *This is what VECTIS is now.*
2. **Part 2 — the V1 legacy demo (California Case Study).** The **origin**: a reactive
   pipeline on a **fixed California sample**. Shown second, labeled loudly as legacy and
   California-only, so its screenshots are never mistaken for global capability.

Record them as two clearly-titled segments with an on-screen label in each. If you only
have time for one, record **Part 1** — it is the real system.

> **Honesty caveat to keep on screen / in narration once:** VECTIS's *scale and machinery*
> are real; its *hazard numbers are not yet calibrated* against real historical labels —
> every deployed coefficient is an honestly-marked illustrative prior
> (`docs/calibration_report.md`). Say this out loud; do not imply validated forecasts.

**Recording setup**
- Browser at 1920×1080, OS dark mode, no bookmarks bar; dark terminal, large monospace.
- Prep terminals before recording: `cd backend && make api` (:8000) and
  `cd frontend && npm run dev` (:5173). Keep a third terminal for live commands.
- On-screen title cards: **"PART 1 — V4 GLOBAL TERMINAL (worldwide, live)"** and
  **"PART 2 — V1 LEGACY DEMO (California case study)"**.

---

## PART 1 — The V4 Global Terminal (≈ 2:00)

**Title card:** `V4 GLOBAL TERMINAL — the planet-scale system`

### 0:00 – 0:20 · The world, live
**On screen:** browser → `http://localhost:5173/terminal`. The `WorldRiskMap` fills the
screen: an H3 choropleth of per-hazard risk across **every continent**.
**Action:** slowly pan/zoom the map — Americas, Europe/Africa, Asia, Oceania — showing
cells recolor as the viewport resolves.
**Narration:**
> "This is the VECTIS Global Terminal. Not one region — the whole planet, on a global grid,
> scored live from real feeds: NASA FIRMS fire, USGS quakes, GDACS multi-hazard, Open-Meteo."

### 0:20 – 0:45 · The event tape + tiering, explained
**On screen:** the `GlobalEventTicker` tape scrolling worldwide detections.
**Narration:**
> "Every active cell gets a cheap screening score every tick. Only cells that genuinely
> heat up get promoted to expensive deep analysis — Monte Carlo, then an AI board. That
> tiering is what makes a *planet* computationally affordable: compute follows real
> events and where operators are actually looking, never viewer-count times grid-size."

### 0:45 – 1:15 · Drill-down that is honest by construction
**On screen:** click a **low-activity** cell → `RegionBriefPanel` shows flat screening bars
+ a **"screening estimate only"** badge. Then click a **promoted (hot)** cell → full
**p05/p50/p95** whiskers, the Bayesian posterior, and the analyst brief.
**Narration:**
> "The drill-down never bluffs. An un-analyzed cell says so — screening estimate only. A
> promoted cell shows the full distribution and a narrated brief. The difference is
> behavioral, not a label."

### 1:15 – 1:35 · Watchlist + playback (memory)
**On screen:** pin a cell to the `WatchlistPanel`; then toggle **playback** — the amber
inset ring + timestamped banner + scrub bar make it unmistakably *not live*.
**Narration:**
> "Pin the cells you care about and they get priority within the budget. And it has a
> memory: scrub back through a cell's risk-and-belief history — always amber, never
> mistaken for live, one click back to now."

### 1:35 – 2:00 · Scale + the honest bottleneck
**On screen:** cut to a terminal. Run:
```bash
make global-stress
```
**Action:** hold on the results table and the FINDING line.
**Narration:**
> "And it's honestly benchmarked. Forty thousand cells going critical at once: cycle
> latency and memory stay flat, the hard budgets never break, and it tells you the truth —
> the AI-board narration budget is the tightest bottleneck. It degrades into a deeper
> queue, never a melted cycle."
**End of Part 1 card:** `Global Terminal — worldwide · live · tiered · bounded`.

---

## PART 2 — The V1 Legacy Demo: California Case Study (≈ 1:30)

**Title card:** `V1 LEGACY DEMO — California only. NOT the global system.`
Keep a persistent corner label reading **"V1 · California case study"** for this whole
segment.

### 0:00 – 0:15 · Frame it as history, up front
**On screen:** the sidebar — point at the **"V1 Legacy Demo"** section and its amber
in-app banner on the **California Case Study** page (`/risk`).
**Narration:**
> "This is where VECTIS started: a reactive pipeline from Session 1. It is a fixed
> **California** demo — a separate, historical system, **not** part of the global terminal.
> The app labels it as such on every screen."

### 0:15 – 0:35 · The reactive pipeline in the terminal
**On screen:** a terminal. Run:
```bash
python -m vectis.scripts.demo   # V1: one reactive Decision Report (make demo)
```
**Narration:**
> "It runs a six-agent board — data discovery, analysis, ML research, simulation, report,
> and a mandatory critic — over a logistic-regression model trained on a 240-cell
> California sample. Offline, no API key."

### 0:35 – 1:00 · The SHAP-driven report
**On screen:** browser → `/risk`, pick **California, USA**, **Run analysis**, then open the
report (`/reports` → a row). Show the risk score, the SHAP-attributed drivers, and the
critic verdict.
**Narration:**
> "The output is a Decision Intelligence Report: a risk score, the model-attributed drivers
> via SHAP, and an AI critique. Every screenshot here is **California** — the model was
> never trained anywhere else."

### 1:00 – 1:30 · Draw the line explicitly, and close
**On screen:** split-screen or quick cut between `/risk` (California grid) and `/terminal`
(the world).
**Narration:**
> "So: two systems. The **Global Terminal** is the planet, live, region-agnostic. The
> **California Case Study** is the original reactive demo, bound to one training sample.
> They share a look, not a scope — and VECTIS says which is which, everywhere."
**End card:** repo URL + `github.com/<you>/vectis`.

---

## The Math Firewall (mention in whichever part covers the board)
Both systems narrate with an AI board, and both obey the **Math Firewall**: the LLM writes
prose, never numbers. Every figure on any report is copied from the deterministic engine.

## Exact assets referenced
- **V4 Global Terminal:** route `/terminal`; stress `make global-stress`
  (`backend/scripts/global_stress_test.py`); tiles `GET /api/v1/tiles`.
- **V1 legacy demo:** `python -m vectis.scripts.demo` (alias `make demo`); routes `/risk`
  (California Case Study) and `/reports` (Case Study Reports), both under the sidebar's
  **V1 Legacy Demo** section.
- **V2 dashboard (optional B-roll):** route `/dashboard`; `python -m vectis.scripts.demo_v2`
  (`make demo-v2`); live ingest `POST /api/v1/stream/ingest` → Probability Timeline.
