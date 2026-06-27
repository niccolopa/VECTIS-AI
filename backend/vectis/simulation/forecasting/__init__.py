"""Forecasting — the public, serializable output the rest of the system consumes.

Adapts a :class:`~vectis.simulation.schemas.SimulationRun` into a horizon-oriented
``Forecast`` for the API, frontend, and V1 Analyst agents — decoupling *what was
forecast* from *how it was computed*. Deliberately empty until the engine produces
runs to adapt (Session 7).
"""
