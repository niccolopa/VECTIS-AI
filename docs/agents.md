# The Multi-Agent System

VECTIS threads a shared, typed `AgentState` through an explicit DAG of small, testable
agents, gated by a mandatory Critic. The same agents run under **two interchangeable
orchestration engines** (see *Orchestration engines* below).

```
Discovery → Analyst → ML Research → Simulation → Report ⟲ Critic
```

## How an agent works

Each agent subclasses `Agent` (`backend/vectis/agents/base.py`) and implements
`_execute(state, ctx) -> StepResult`. The base class times the step and appends an
auditable `AgentTrace`. Agents read/write the shared `AgentState`; bulky artifacts live
on the `RunContext` blackboard.

```python
class MyAgent(Agent):
    name = "my_agent"

    def _execute(self, state: AgentState, ctx: RunContext) -> StepResult:
        ...                      # read state / ctx.artifacts, do work
        state.signals.append(...)
        return StepResult(summary="what I did", payload={...}, used_llm=False)
```

## The agents

| Agent | Question | Responsibility |
|---|---|---|
| **Data Discovery** | — | Acquire raw data via the connector; record sources/coverage. |
| **Data Analyst** | *What is happening?* | Run the pipeline; compute descriptive signals. |
| **ML Research** | *What could happen next?* | Predict per-cell + aggregate risk; attach SHAP drivers. |
| **Simulation** | *What if?* | Perturb climate drivers; re-score scenarios. |
| **Report** | — | Compose the `DecisionReport`; narrate the summary via the LLM. |
| **Critic** | *Is this justified?* | Challenge claims; gate the report. **Mandatory.** |

Each agent also declares a one-line `responsibility` (see `agent.responsibility`),
surfaced here and via introspection.

## Orchestration engines

Both engines implement the same `BaseOrchestrator` interface
(`backend/vectis/agents/runtime.py`) over the *same* `AgentSuite`, so they can never
diverge in which agents run or how a run is set up. Select via `VECTIS_ORCHESTRATOR`.

| Engine | Module | When |
|---|---|---|
| **`custom`** (default) | `orchestrator.py` | Deterministic, dependency-light, offline. The whole control flow reads in one file. Best for CI/demos. |
| **`langgraph`** | `langgraph_engine.py` | Same flow as a LangGraph `StateGraph` (conditional Critic edge). Buys the LangGraph runtime + a path to checkpointing/streaming. Requires the `langgraph` extra. |

The shared runtime guarantees **parity**: for the same input both engines produce an
identical `DecisionReport` (asserted in `tests/integration/test_langgraph_orchestrator.py`).
The custom engine is the default so VECTIS stays zero-dep and offline by default; switching
is a one-line config change (`pip install -e '.[langgraph]'` + `VECTIS_ORCHESTRATOR=langgraph`).

```
                custom engine                         langgraph engine
   ┌─────────────────────────────┐         START → discovery → analyst → ml_research
   │ for agent in evidence_stages│                 → simulation → report → critic
   │     agent.run(state, ctx)   │                        │
   │ report.run(); critic.run()  │      (blocker & revisions left) ──► report
   │ while not approved & < max:  │                        │
   │     report.run(); critic.run│                       END
   └─────────────────────────────┘
```

## The Critic (mandatory)

The Critic (`backend/vectis/agents/critic.py`) is VECTIS's adversarial quality gate. It is
deterministic and rule-based by design — a validation gate must be reliable. It checks:

- **Evidence**: every headline driver must be referenced by an `Evidence` item.
- **Consistency**: risk score in range; confidence not overstated on thin evidence.
- **Actions**: present, and severe/high risk must carry a high-priority action.

Findings are `CriticIssue`s with severity `info | warning | blocker`. Any **blocker**
marks the report unapproved and triggers a revision by the Report agent (which drops the
flagged claims), up to `VECTIS_CRITIC_MAX_REVISIONS`. The verdict always travels with the
report, approved or not — the human decides.

> LLM-assisted critique (surfacing subtler weak assumptions) is a roadmap item layered
> *on top of* — never replacing — these invariants.

## The LLM provider

Agents call the LLM only to **narrate** already-computed, evidence-backed findings,
always passing a deterministic `fallback`:

```python
result = self.llm.narrate(instruction="…", context={…}, fallback=deterministic_text)
```

- `MockProvider` (default) returns the fallback verbatim → reproducible, offline.
- `AnthropicProvider` uses Claude when `VECTIS_LLM_PROVIDER=claude` + a key is set, and
  degrades to the fallback on any error.

The LLM never invents numbers, so explainability and reproducibility hold regardless of
provider.

## Adding an agent

1. Create `backend/vectis/agents/my_agent.py` subclassing `Agent`.
2. Add it to the DAG in `Orchestrator.__init__`/`run`.
3. If it adds claims to the report, emit matching `Evidence` so the Critic passes.
4. Add an integration test asserting it appears in `report.trace`.
