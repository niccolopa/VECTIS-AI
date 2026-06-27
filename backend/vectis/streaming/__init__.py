"""Real-time intelligence layer — connect live data streams to the V2 engines.

This package is the **orchestration glue** between incoming real-world events and
the pure-math simulation engines (``simulation/``). An event arrives → it becomes
an :class:`~vectis.simulation.probability.bayesian.Observation` → the
:class:`~vectis.streaming.updater.RealTimeUpdater` runs the Bayesian update,
decides whether the belief shift is large enough to warrant a fresh Monte Carlo
run, and emits a :class:`~vectis.streaming.events.StateChange` for broadcast.

Deliberately **infrastructure-light**: in-memory state, an in-process WebSocket
broadcaster, and FastAPI ``BackgroundTasks`` for async execution — no Kafka/Redis.
The seam is :class:`RealTimeUpdater.process` (pure, synchronous, transport-agnostic);
swapping in Celery/Kafka/Redis later means changing *who calls it and how the
result is published*, never the math it wraps.
"""
