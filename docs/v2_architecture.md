# VECTIS V2 — System Architecture

VECTIS V2 is a **real-time probabilistic decision-intelligence platform**. It turns
a stream of real-world observations into *distributions over possible futures* —
not single point predictions — and narrates them with an auditable AI board whose
numbers are produced entirely by deterministic math.

This document maps the end-to-end flow and ties each stage to the code that
implements it.

---

## The end-to-end flow

```mermaid
flowchart TD
    subgraph EXT["🌍 External World"]
        FIRMS["NASA FIRMS<br/>active-fire detections<br/><i>(V3)</i>"]
        SENSOR["Sensor readings<br/>temp · humidity · wind"]
        ALERT["Weather alerts"]
    end

    subgraph API["⚡ API Layer · FastAPI"]
        INGEST["POST /stream/ingest<br/><b>202 Accepted</b> immediately"]
        DASH["GET /dashboard/twins/:id<br/>POST /dashboard/simulate/what-if"]
        WS(("WS /stream/ws<br/>live push"))
    end

    subgraph RT["🔁 Real-Time Layer"]
        UPDATER["RealTimeUpdater<br/><i>routes event → region twin</i>"]
    end

    subgraph TWIN["🛰️ Digital Twin · RegionTwin (California)"]
        STATE["WorldState<br/>temp · rainfall · wind · ignition"]
        BAYES["Bayesian Update<br/>GaussianBayesianUpdater<br/><i>posterior belief over scenarios</i>"]
        GATE{"belief shift<br/>&gt; threshold?"}
    end

    subgraph ENGINE["🎲 Monte Carlo Engine · pure NumPy/SciPy"]
        SHARD["SeedSequence.spawn<br/><i>reproducible sharding</i>"]
        MC["Vectorized simulation<br/><b>100k – 1M scenarios</b>"]
        CACHE[("TTL + LRU cache<br/>warm hit ≈ 6000× faster")]
        RISK["RiskState + per-scenario<br/>ProbabilityDistributions<br/>p05 · p50 · p95 · exceedance"]
    end

    subgraph BOARD["🧠 LangGraph Analyst Board · Math Firewall"]
        ANALYST["Analyst"] --> SCEN["Scenario"]
        SCEN --> DEBATE["Debate<br/>optimist ⚔ pessimist"]
        DEBATE --> CRITIC["Red-Team Critic"]
        CRITIC --> REPORT["DecisionIntelligenceReport<br/><i>prose only — numbers copied in</i>"]
    end

    subgraph UI["🖥️ React Dashboard · Enterprise Tactical"]
        EXPLORER["Scenario Explorer<br/>box-and-whisker"]
        TIMELINE["Probability Timeline<br/>risk × confidence"]
        WHATIF["What-If Simulator"]
        BRIEF["AI Intelligence Brief"]
    end

    FIRMS & SENSOR & ALERT -->|HTTP event| INGEST
    INGEST -->|BackgroundTask| UPDATER
    UPDATER --> STATE --> BAYES --> GATE
    GATE -->|yes| SHARD
    GATE -->|no: reuse last| RISK
    SHARD --> MC
    MC <--> CACHE
    MC --> RISK
    RISK -->|StateChange| WS
    RISK -->|read-only numbers| ANALYST
    REPORT --> DASH
    RISK --> DASH
    DASH --> EXPLORER & WHATIF & BRIEF
    WS -->|live updates| TIMELINE

    classDef math fill:#0b3d2e,stroke:#00ffd5,color:#d6fff5;
    classDef llm fill:#3d2c0b,stroke:#ffb800,color:#fff3d6;
    class STATE,BAYES,SHARD,MC,CACHE,RISK math;
    class ANALYST,SCEN,DEBATE,CRITIC,REPORT llm;
```

**The Golden Rule (Math Firewall).** Everything in green is deterministic
`numpy`/`scipy` — no LLM ever touches a number. Everything in amber is the LLM
board, which only *reads* the engine's output and writes prose. The boundary is
enforced structurally: nothing under `simulation/` imports `vectis.agents`, and
every numeric field on `DecisionIntelligenceReport` is copied from `BoardInput`
(the engine's verdict), never generated.

---

## What happens when an observation arrives

```mermaid
sequenceDiagram
    participant Src as Sensor / FIRMS
    participant API as /stream/ingest
    participant U as RealTimeUpdater
    participant T as RegionTwin
    participant E as Monte Carlo Engine
    participant B as Analyst Board
    participant WS as WebSocket
    participant UI as Dashboard

    Src->>API: POST event (temp +4°C)
    API-->>Src: 202 Accepted (never blocks)
    API->>U: BackgroundTask
    U->>T: route to "california" twin
    T->>T: Bayesian update of scenario beliefs
    alt belief shifted materially
        T->>E: re-run Monte Carlo (cached)
        E-->>T: RiskState + distributions
    else negligible shift
        T-->>T: reuse last RiskState
    end
    T->>WS: broadcast StateChange
    WS-->>UI: live risk + timeline point
    UI->>B: (on demand) request brief
    B-->>UI: DecisionIntelligenceReport
```

The ingest path returns **202 immediately** and hands the CPU-bound math to a
background worker thread — ingestion is never blocked by computation. A re-run only
happens when the posterior belief moves past a threshold; otherwise the last
`RiskState` is reused (and the cache makes even a forced re-run on an unchanged
state near-instant).

---

## Component → code map

| Stage | Responsibility | Code |
| --- | --- | --- |
| Ingest / stream | Async accept, route, broadcast | `vectis/api/routers/stream.py`, `vectis/streaming/` |
| Real-time updater | Event → twin routing | `vectis/streaming/updater.py` |
| Digital twin | State + belief, re-run policy | `vectis/digital_twin/entities/region.py` |
| Bayesian update | Posterior over scenarios | `vectis/simulation/probability/bayesian.py` |
| Monte Carlo engine | Vectorized 100k–1M scenarios | `vectis/simulation/engine/runner.py` |
| Caching | TTL + LRU memoization | `vectis/simulation/caching.py` |
| Distributed (stub) | Ray/Dask abstraction | `vectis/simulation/engine/distributed.py` |
| Analyst board | LangGraph narration | `vectis/agents/board/` |
| Dashboard API | View-models for the UI | `vectis/services/dashboard_service.py`, `vectis/api/routers/dashboard.py` |
| React dashboard | Visualization | `frontend/src/pages/DashboardPage.tsx`, `frontend/src/features/dashboard/` |

---

## Reproducibility & scale (Session 13)

The engine is reproducible per `(seed, n_workers)`: draws are sharded with
`numpy.random.SeedSequence.spawn`, so serial, multiprocessing, and the distributed
stub all produce **byte-identical** results. On a 12-core dev machine a 1,000,000 ×
3-branch run (3M trajectory evaluations) completes in **~0.8 s single-thread** at
~72 MB peak — see `docs/v2_simulation_engine.md` §10 and `make stress`. For this
cheap vectorized math, multiprocessing is *slower* (process spawn + pickling cost
more than the compute), so it stays off by default — documented honestly rather
than hidden.
