"""Digital Twin layer — living, stateful models of real-world entities.

A **Digital Twin** is the business-logic object that *uses* the V2 math engines.
The engines (``simulation/``) are generic calculators — they know nothing about
"California" or "wildfire". A twin owns a region's (or, later, a market's) physical
**state**, evolves it deterministically as observations arrive
(``transitions/``), and asks the probabilistic engines to compute its future
**risk state**.

Architecture (read top-down):
- ``entities/base.py`` — the :class:`DigitalTwin` ABC every twin implements.
- ``entities/region.py`` — the first concrete twin: :class:`RegionTwin` (Climate
  Risk). A ``FinancialMarketTwin`` would sit beside it, same ABC.
- ``state/manager.py`` — an in-memory registry of active twins.
- ``transitions/base.py`` — deterministic state-evolution rules (heuristics, not
  physics engines).
- ``schemas.py`` — the twin's output contracts (:class:`RiskState`, ``TwinUpdate``).

Layering: ``streaming`` (Session 9) depends on ``digital_twin``; ``digital_twin``
depends only on ``simulation`` + ``core`` — never the reverse, never on an LLM.
"""
