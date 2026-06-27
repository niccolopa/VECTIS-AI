"""Real-time orchestrator — route live events to digital twins.

Since Session 10, the belief/risk state lives inside :class:`~vectis.digital_twin.
entities.region.RegionTwin` objects held in a :class:`~vectis.digital_twin.state.
manager.StateManager`. :class:`RealTimeUpdater` is now a thin **router**:

1. **Debounce** content-duplicate events (so 100 identical readings/sec don't
   become 100 updates — also keeping the Bayesian math honest).
2. **Route** the event to its region's twin via the manager.
3. **Delegate** to ``twin.update_from_observation`` (deterministic transition →
   Bayesian update → conditional Monte Carlo re-run — all inside the twin).
4. **Wrap** the twin's :class:`TwinUpdate` in a transport-level :class:`StateChange`.

``process`` stays **pure, synchronous, and transport-agnostic** — the swappable
seam. FastAPI BackgroundTasks call it today; a Celery/Kafka worker could call the
exact same method tomorrow. The CPU-bound math now lives in the twin; the router
only debounces and dispatches, so its lock is held briefly (per-twin locks inside
the twins do the real serialization — that scales to many regions).
"""

from __future__ import annotations

import threading
import time

from vectis.core.logging import get_logger
from vectis.digital_twin.entities.region import RegionTwin
from vectis.digital_twin.schemas import RiskState
from vectis.digital_twin.state.manager import StateManager
from vectis.streaming.events import StateChange, StreamEvent

log = get_logger(__name__)

_DEFAULT_REGION = "liguria"


class RealTimeUpdater:
    """Route incoming events to the right digital twin and emit state changes."""

    def __init__(
        self,
        manager: StateManager,
        *,
        debounce_seconds: float = 1.0,
        default_region: str = _DEFAULT_REGION,
    ) -> None:
        self._manager = manager
        self._debounce_seconds = debounce_seconds
        self._default_region = default_region
        self._debounce_lock = threading.Lock()
        self._recent: dict[str, float] = {}  # dedupe_key → monotonic time last seen

    @property
    def manager(self) -> StateManager:
        return self._manager

    def risk_state(self, region: str | None = None) -> RiskState | None:
        """Current risk picture for ``region`` (default region if omitted)."""
        twin = self._manager.get(region or self._default_region)
        return twin.computed_risk_state if isinstance(twin, RegionTwin) else None

    def process(self, event: StreamEvent) -> StateChange | None:
        """Apply one event to its twin. Returns a :class:`StateChange`, or ``None``
        if the event was debounced or no twin is registered for its region.

        Synchronous and transport-agnostic: safe to call from a background task,
        a thread, or a future Celery/Kafka worker.
        """
        if self._is_duplicate(event):
            log.info("stream.debounced", event_id=event.event_id, region=event.region)
            return None

        twin = self._manager.get(event.region)
        if not isinstance(twin, RegionTwin):
            log.warning("stream.no_twin", event_id=event.event_id, region=event.region)
            return None

        update = twin.update_from_observation(event.to_observation())
        return StateChange(
            event_id=event.event_id,
            triggered_rerun=update.recomputed,
            belief_shift=update.belief_shift,
            risk=update.risk_state,
        )

    # ── internals ────────────────────────────────────────────────────────────
    def _is_duplicate(self, event: StreamEvent) -> bool:
        """Content-debounce: True if this measurement was seen within the window.

        ponytail: in-memory dict + monotonic clock — the blueprint. Swap for a
        Redis key with TTL when ingestion is multi-process.
        """
        if self._debounce_seconds <= 0.0:
            return False
        with self._debounce_lock:
            now = time.monotonic()
            key = event.dedupe_key()
            last = self._recent.get(key)
            # Evict stale keys so the map can't grow unbounded.
            self._recent = {
                k: t for k, t in self._recent.items() if now - t < self._debounce_seconds
            }
            self._recent[key] = now
            return last is not None and (now - last) < self._debounce_seconds


def build_default_updater() -> RealTimeUpdater:
    """Construct the real-time updater with the Liguria climate-risk twin registered.

    ponytail: single region for now. Register more ``RegionTwin``s (or other twins)
    on the same manager as regions are added.
    """
    manager = StateManager()
    manager.register(RegionTwin("liguria"))
    return RealTimeUpdater(manager)
