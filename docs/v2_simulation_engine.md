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
