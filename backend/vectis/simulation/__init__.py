"""VECTIS V2 — the Simulation & Forecasting Engine.

A **pure mathematical service**. Given the current estimated state of the world,
it generates plausible futures and their probabilities via Monte Carlo
simulation. It depends only on numerical libraries (``numpy``/``scipy``/``pymc``),
Pydantic, and the shared ``core`` vocabulary — **never** on ``vectis.agents``.

The Golden Rule of V2: **LLMs never compute math here.** All calculation lives
behind the deterministic/probabilistic interfaces in this package; LLM "Analyst"
agents (V1) only read the numerical output.

Subpackages:
- ``states``       — State Estimation: build the digital-twin ``WorldState``.
- ``scenarios``    — Scenario Generation: branch the state into weighted futures.
- ``models``       — Stochastic (mathematical) models a trajectory obeys.
- ``engine``       — Monte Carlo execution.
- ``probability``  — Bayesian updating and distribution reduction.
- ``forecasting``  — the public ``Forecast`` output interface.

See ``docs/v2_simulation_engine.md`` for the architecture and flow.
"""
