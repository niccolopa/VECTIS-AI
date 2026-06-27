"""Models — stochastic *mathematical* models a single MC trajectory obeys.

NOT database/ORM models. These are the laws of motion for a simulated future:
e.g. a random walk on risk, a Markov chain over :class:`RiskBand`, a hazard
process. Each will implement a small, seedable ``step``/``sample`` interface the
engine calls per iteration. Deliberately empty until Session 7 — the concrete
process is chosen alongside the Monte Carlo implementation.
"""
