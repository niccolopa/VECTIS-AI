# V2 — The Simulation & Forecasting Engine

> Status: **Monte Carlo engine implemented (Session 7)**. Session 6 defined the
> blueprint and contracts; Session 7 implemented the concrete vectorized engine
> (`engine/`, `models/`, `scenarios/generator.py`) — 100k samples in ~70 ms,
> reproducible and optionally parallel. State Estimation and Bayesian updating
> remain interfaces (Session 8). See `backend/vectis/simulation/`.

---

## 1. From V1 (Reactive) to V2 (Predictive / Probabilistic)

**V1** (Sessions 1–5) answers *"What is happening, and why?"* It ingests data,
runs an ML model, attributes drivers with SHAP, and has LLM agents narrate an
explainable `DecisionReport`. It is **reactive**: it describes the present.

**V2** answers a fundamentally different question:

> *Given the current state of the world, what are all plausible futures, and with
> what probability will each occur?*

V2 is **predictive and probabilistic**. It does not produce a single number; it
produces a **distribution over outcomes**. Where V1 says *"risk is 76.7/100,"* V2
says *"there is a 31% probability the region enters the SEVERE band within 30
days, with a 90% credible interval of [58, 84]."*

### The Golden Rule of V2

**LLMs are never used for mathematical, probabilistic, or statistical
calculation.** LLMs hallucinate math. The numerical engine is built exclusively
from deterministic and probabilistic Python libraries (`numpy`, `scipy`, and —
when Bayesian updating lands — `pymc`).

LLMs re-enter only at the very end, as **Analysts**: they read the *numerical
output* of the engine and phrase it for humans. They never compute it. This is
the same "LLM-narrates-not-decides" discipline V1 established, now enforced at
the layer boundary: everything inside `simulation/` is pure math.

---

## 2. Architecture — the V2 flow

```
                          ┌─────────────────────────────────────────────┐
                          │              V2 SIMULATION ENGINE            │
                          │            (pure math — no LLMs)             │
  External Data           │                                             │
  ┌───────────────┐       │  ┌──────────────────┐                       │
  │ NASA FIRMS    │       │  │ State Estimation │  digital twin of      │
  │ ERA5 weather  │──────────▶│  (states/)      │  the world *now*,     │
  │ Copernicus    │       │  │                  │  with uncertainty     │
  │ (V1 features) │       │  └────────┬─────────┘                       │
  └───────────────┘       │           │ WorldState                      │
                          │           ▼                                 │
                          │  ┌──────────────────┐                       │
                          │  │ Scenario         │  branch the future    │
                          │  │ Generation       │  into weighted        │
                          │  │ (scenarios/)     │  hypotheses           │
                          │  └────────┬─────────┘                       │
                          │           │ ScenarioSet (priors sum to 1)   │
                          │           ▼                                 │
                          │  ┌──────────────────┐                       │
                          │  │ Monte Carlo      │  draw N stochastic    │
                          │  │ Simulation       │  trajectories per     │
                          │  │ (engine/ +       │  scenario             │
                          │  │  models/)        │                       │
                          │  └────────┬─────────┘                       │
                          │           │ raw outcome samples             │
                          │           ▼                                 │
                          │  ┌──────────────────┐                       │
                          │  │ Probabilistic    │  ProbabilityDistribution
                          │  │ Output           │  (mean, CI, P(exceed))│
                          │  │ (probability/ +  │  + Bayesian update as  │
                          │  │  forecasting/)   │  new data arrives      │
                          │  └────────┬─────────┘                       │
                          └───────────┼─────────────────────────────────┘
                                      │ Forecast (numbers only)
                                      ▼
                          ┌──────────────────────────┐
                          │   Agent Analysis (V1)    │  LLM reads the numbers
                          │   "Analyst" agents       │  and narrates them.
                          │   — narrate, never compute│  NEVER does the math.
                          └──────────────────────────┘
```

**Flow in words:** External data (and the existing V1 feature pipeline) feed
**State Estimation**, which builds a *digital twin* — the best estimate of the
world right now, *with uncertainty attached*. **Scenario Generation** branches
that state into a set of weighted future hypotheses (priors summing to 1). The
**Monte Carlo** engine draws `N` stochastic trajectories per scenario through a
chosen stochastic **model**. The resulting samples are reduced to
**Probability Distributions** and **Forecasts** — and **Bayesian updating**
revises scenario priors as real-world observations come in. Only then do the V1
**Analyst** agents read those numbers and explain them.

---

## 3. Core concepts

| Concept | Where | Definition |
|---|---|---|
| **State** (`WorldState`) | `states/` | A digital-twin snapshot of the world at a point in time: the estimated value of each variable **plus its uncertainty**. Not a point — a starting distribution. |
| **Scenario** | `scenarios/` | A named, parameterized hypothesis about how the future unfolds (a set of perturbations to the state) carrying a **prior probability**. A `ScenarioSet`'s priors must sum to 1. |
| **Simulation Run** (`SimulationRun`) | `engine/` | One execution of the engine: a `SimulationConfig` (N iterations, RNG seed, horizon) applied to a `WorldState` × `ScenarioSet`, producing per-scenario outcome samples. **Seeded ⇒ reproducible.** |
| **Probability Distribution** | `probability/` | The reduction of raw Monte Carlo samples for one outcome variable into summary statistics: mean, std, credible interval, and threshold-exceedance probabilities (e.g. P(risk ≥ SEVERE)). |

Supporting concepts:

- **Stochastic Model** (`models/`) — the mathematical law a single Monte Carlo
  trajectory obeys (e.g. a random walk, a Markov chain over risk bands, a
  hazard process). Statistical/mathematical models — **not** ORM/DB models.
- **Forecast** (`forecasting/`) — the public, serializable output object the
  rest of the system (API, agents, frontend) consumes: distributions over a
  horizon, decoupled from how they were computed.
- **Bayesian Update** (`probability/`) — the rule that revises scenario priors
  (and state estimates) when new observations arrive, so the engine learns.

---

## 4. Forward-compatibility & decoupling

`backend/vectis/simulation/` is a **pure mathematical service**. It depends only
on `numpy`/`scipy`/`pymc`, Pydantic, the stdlib, and the shared `core` vocabulary
(e.g. `RiskBand`). It does **not** import `vectis.agents` — the dependency points
the other way: agents (V1) will read V2's `Forecast` output, never the reverse.
This means the engine can run headless as a service, be tested without any LLM or
agent machinery, and be reused by other frontends.

> **Naming note (reconciliation):** the Session 6 brief specified
> `backend/app/simulation/`. This repository's package is `backend/vectis/`, and a
> parallel `backend/app/` tree was deliberately considered and rejected in earlier
> sessions (see `HANDOFF.md` → *What Didn't Work*). To honor the source of truth
> and avoid duplicating a working, tested package, V2 lives under
> `backend/vectis/simulation/`.

---

## 5. Bayesian update & confidence (Session 8)

The Monte Carlo engine turns a `WorldState` + `ScenarioSet` (priors) into
distributions. Session 8 closes the **learn-from-data loop**: when a real
observation arrives, revise *which future we believe in*, then re-run.

**`probability/bayesian.py` — `GaussianBayesianUpdater`.** Each scenario predicts
a value for the observed variable (the state estimate plus the scenario's
perturbation). The likelihood of an observation under a scenario is the Gaussian
density of the observed value at that prediction, and Bayes' theorem gives the
posterior:

```
P(scenario | obs) = P(obs | scenario) · P(scenario) / P(obs)
P(obs | scenario) = N(obs.value ; mean = predicted_value(scenario), sigma)
sigma             = hypot(model_std, observation.std)
P(obs)            = Σ_s P(obs | s) · P(s)        ← evidence (the denominator)
```

The evidence is handled **exactly** by normalizing over the (finite, exhaustive)
scenario set, so the returned `ScenarioSet` priors sum to 1 by construction —
ready to feed straight back into the next `MonteCarloEngine.run`. Computation is
in log-space (stabilized by subtracting the max log-posterior) so a sharp
observation can drive a likelihood to ~0 without underflowing to a degenerate
all-zero posterior. `update_batch` sums log-likelihoods across conditionally-
independent observations → a true **joint** update, independent of arrival order.

**`probability/uncertainty.py` — the Confidence Score.** Confidence is *inversely*
related to spread. Categorical (over a `ScenarioSet`): `1 − normalized Shannon
entropy` — a uniform posterior scores 0, all mass on one scenario scores 1, so
consistent observations (which sharpen the posterior) raise it and contradictory
ones lower it. Continuous (over a `ProbabilityDistribution`): `1 / (1 + (std/scale)²)`.

**`probability/calibration.py` — blueprint.** `brier_score` (mean squared error of
predicted-vs-actual) is implemented and tested; the reliability diagram and a
fitted recalibration map (isotonic / Platt) are stubbed until a real FIRMS-label
outcome backlog exists.

**Zero-LLM, vectorized.** Pure `numpy`/`scipy`; updating 1,000 observations takes
well under a millisecond (one vectorized `norm.logpdf` per observation across the
scenario set). The Liguria use case (`python -m vectis.simulation.probability.bayesian`):
a +3.5 °C temperature spike moves `hotter_drier` from prior 0.30 to posterior 0.92,
fire risk 88 → 94 / 100, confidence 6% → 71%.

---

## 6. Real-time intelligence layer (Session 9)

The math engines are batch services. Session 9 wraps them in a **continuous
updating loop** so live data keeps the forecast current — without heavy infra
(no Kafka/Redis yet), and structured so that infra can drop in later.

**Flow.** `POST /api/v1/stream/ingest` accepts an event (`SensorReading` /
`WeatherAlert`, a `kind`-discriminated union) and returns **202 Accepted
immediately**, scheduling the work on a FastAPI `BackgroundTask`. The task:

```
event ─▶ Observation ─▶ debounce ─▶ Bayesian update ─▶ belief_shift (TV distance)
        │                                                     │
        │                              shift ≥ threshold ─▶ re-run Monte Carlo
        ▼                                                     ▼
   RealTimeUpdater.process()  ───────────────────────▶  StateChange ─▶ WebSocket broadcast
```

- **`streaming/events.py`** — inbound events (each `to_observation()` maps itself
  to the Session-8 `Observation`) and outbound `RiskState` / `StateChange`.
- **`streaming/updater.py`** — `RealTimeUpdater.process(event)` is **pure,
  synchronous, transport-agnostic**: debounce → Bayesian update → decide (re-run
  Monte Carlo iff the prior→posterior **total-variation distance** ≥ threshold) →
  build `RiskState`. An internal lock guards the in-memory belief state.
- **`streaming/broadcaster.py`** — `ConnectionManager`, an in-process WebSocket
  fan-out (`WS /api/v1/stream/ws`); the only component that knows about sockets.

**Async handling.** The CPU-bound `process()` runs via `asyncio.to_thread` inside
the background task, so the event loop (and ingestion) is never blocked; the
broadcast then runs back on the loop. **Debouncing**: content-duplicate events
(same source+variable+value) inside a 1 s window are dropped — which also keeps
the Bayesian math honest (one measurement counted once).

**Decoupling.** `RealTimeUpdater` imports zero web/transport code; the router and
broadcaster are the only FastAPI-aware pieces. Replacing BackgroundTasks with
Celery/Kafka means rewriting the dispatch glue (the router task) and the publish
transport (the broadcaster) — `process()` and all of `simulation/` are untouched.

---

## 7. Digital Twin layer (Session 10)

The math engines are generic calculators; the streaming layer moves data. Session
10 adds the **entity** that ties them to the real world: a **Digital Twin** owns a
region's physical state, evolves it as data arrives, and drives the engines to keep
its risk current. Layering: `streaming → digital_twin → simulation/core` (never the
reverse, never an LLM).

```
                         vectis/digital_twin/
  ┌────────────────────────────────────────────────────────────────┐
  │ entities/base.py   DigitalTwin ABC  (get_current_state /         │
  │                    update_from_observation / predict_risk)       │
  │ entities/region.py RegionTwin  ── physical RegionState:          │
  │                      temperature_anomaly, humidity_level,        │
  │                      vegetation_stress, recent_fire_history,     │
  │                      + computed_risk_state                       │
  │ transitions/base.py ClimateTransition (deterministic heuristics) │
  │ state/manager.py    StateManager (in-memory twin registry)       │
  │ schemas.py          RiskState, TwinUpdate                        │
  └────────────────────────────────────────────────────────────────┘
```

**Deterministic transitions → probabilistic engine.** `update_from_observation`
runs a fixed order so the two roles of an observation stay separate and correct:

1. **Bayesian belief update against the *pre-transition* state** — the observation
   is compared to what each scenario *predicted*, so e.g. a +4 °C reading (vs the
   +2 °C estimate) correctly shifts mass toward the hotter/drier scenario.
2. **Deterministic transition** evolves the *present* physical state
   (`ClimateTransition`: a temperature reading sets `temperature_anomaly`; rain
   raises `humidity_level`; vegetation stress relaxes toward the heat/moisture
   balance `Δstress = temp·K_TEMP − humidity·K_HUM`). Simple heuristics — no physics
   engine.
3. **Monte Carlo re-run** over the *new* state × posterior beliefs (only if the
   state changed or beliefs moved past a threshold), reduced to a `RiskState`
   (`posterior_mixture_risk` + `scenario_confidence`).

The twin's *only* engine-specific knowledge is `_to_world_state()` — the map from
its domain fields onto the engine's `WorldState` variables (humidity → rainfall
anomaly; vegetation stress + recent fires → ignition rate). Swap that mapping, the
transition, and the scenarios and the same engines model a different entity — a
`FinancialMarketTwin` sits beside `RegionTwin` under the same ABC.

**Wired into streaming.** `RealTimeUpdater` (Session 9) is now a thin router:
debounce → `StateManager.get(region)` → `twin.update_from_observation` → wrap the
`TwinUpdate` in a `StateChange` for broadcast. The Liguria twin is registered at
startup; a `WeatherAlert` for "liguria" flows straight into it.

---

## 8. Simulation Analysis Board — LLM agents (Session 11)

Everything in §1–§7 is pure numbers. Session 11 reconnects the LLM layer — but
under the V1 discipline, now enforced as a **Math Firewall**: agents *read* the
engine's output and narrate it; they never recompute or contradict it.

```
   RiskState (from a Digital Twin)
        │   build_input  (numbers copied verbatim — the firewall's source of truth)
        ▼
   ┌──────────  vectis/agents/board/  (LangGraph StateGraph) ──────────┐
   │  Analyst → Scenario Narrator → Debate(Optimist · Pessimist) → Critic │
   └────────────────────────────────────┬──────────────────────────────┘
        ▼
   DecisionIntelligenceReport  (structured Pydantic → JSON for the frontend)
```

- **`board/prompts.py`** — the system prompts. Every agent carries the
  `MATH_FIREWALL` preamble ("you are an analyst, not a calculator; the numbers are
  authoritative ground truth; never recompute or invent figures") and a `TONE`
  preamble enforcing a national-security / institutional-risk register.
- **`board/nodes.py`** — the five analysts (Analyst, Scenario Narrator, Optimist,
  Pessimist, Red-Team Critic). Each builds the numbers into an LLM `context`, writes
  a deterministic intelligence-grade `fallback`, calls `LLMProvider.narrate`, and
  returns a typed object whose **numeric fields are copied from the input**.
- **`board/team.py`** — the LangGraph `StateGraph` (`Analyst → Scenario → Optimist
  → Pessimist → Critic`). Reused via the existing `LLMProvider` abstraction (default
  `mock` → deterministic, offline, key-free), not a hard OpenAI dependency.
- **`board/service.py`** — `SimulationBoardService.analyze_twin(twin)` / `analyze(
  BoardInput)`. Prefers the LangGraph graph; falls back to running the same nodes
  sequentially if LangGraph is absent (identical report — graph is an execution
  choice). Stream-independent: a report can be generated on demand.
- **API:** `POST /api/v1/intelligence/reports` `{region}` → reads the region twin's
  current `RiskState`, runs the board, returns the `DecisionIntelligenceReport`.

**The Math Firewall is structural, not just prompt-deep.** Because every figure in
the report (risk score, confidence, scenario probabilities, residual uncertainty) is
copied from the engine output *in code*, a hallucinated or hostile LLM narration
cannot change a single number — proven by a test that runs the board with a "lying"
LLM and asserts the structured figures are unchanged. The LLM owns prose; the engine
owns arithmetic.

---

## 9. End-to-end demo (Session 12)

Every V2 layer now runs as one offline, deterministic script:
`python -m vectis.scripts.demo_v2` (or `python scripts/run_demo_liguria.py`, or
`make demo-v2`). It drives the full pipeline and renders it as a tactical
intelligence terminal (pure stdlib — no `rich`/dependency):

```
Simulated weather alert (heatwave + drought)
   → RealTimeUpdater  → Liguria RegionTwin deterministic transition
   → Monte Carlo (100,000 scenarios)  → Bayesian posterior update
   → LangGraph Analysis Board  → Decision Intelligence Report
```

Five phases print to the console — INITIALIZE (baseline risk + scenario bars),
OBSERVE (intercepted SIGINT alerts), CALCULATE (per-event twin transition → 100k
Monte Carlo → Bayesian belief shift → recomputed risk), ANALYZE (convene the
board), REPORT (the boxed `DecisionIntelligenceReport`: BLUF, key metrics,
executive summary, scenario projections, blue/gold debate, red-team critique).

For the Liguria use case it shows a calm baseline (~45/100 MODERATE) jump to
~98/100 SEVERE as the heatwave+drought drive the posterior onto the *hotter &
drier* branch — the math and the analyst narrative side by side, Math Firewall
intact (numbers = engine, prose = analysts). Runtime ~1 s, offline, key-free.
`run_demo(...)` returns a `DemoResult` (baseline/final `RiskState` + report) so the
same flow is asserted end-to-end in `tests/integration/test_end_to_end_demo.py`.
