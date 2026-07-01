"""``GlobalScreeningSweep`` — run every registered screen over the active cell set.

This is the layer that will drive the global heat map: on every state update, score
**every currently active cell** with each registered :class:`ScreeningIndex`, hazard by
hazard, and return a flat ``{cell_id: {hazard: ScreeningScore}}`` result.

Two entry points, one guarantee:

- :meth:`GlobalScreeningSweep.sweep` is **pure and synchronous** — it takes an explicit
  batch of cells, does no I/O, no broker calls, no side effects. It composes cleanly into a
  future scheduled sweep, an API endpoint, or a test.
- :meth:`GlobalScreeningSweep.sweep_store` is the convenience that pulls the store's **hot
  set** (``active_cell_ids`` — never the theoretical planet-wide grid) and feeds it to
  :meth:`sweep`. Untouched cells are never materialized; a cell whose state a given hazard
  can't use is simply absent from that hazard's results (the index skips it).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol

from vectis.realtime.events.base import CellId
from vectis.realtime.screening.base import ScreeningIndex, ScreeningScore, default_registry
from vectis.realtime.state.models import WorldCellState

#: One cell's screening result: hazard name → its score. Absent hazards = not screened.
CellScores = dict[str, ScreeningScore]


class ActiveCellStore(Protocol):
    """The minimum a store must offer to be swept: a one-pass read of its active states.

    Satisfied by every :class:`~vectis.realtime.state.store.StateStore`; when the store is an
    :class:`~vectis.realtime.state.store.EvictingStateStore` this is the bounded hot set."""

    def active_states(self) -> list[WorldCellState]: ...


class GlobalScreeningSweep:
    """Score the active cell set with every registered per-hazard screening index."""

    def __init__(self, registry: Mapping[str, ScreeningIndex] | None = None) -> None:
        # Default to the shared registry (wildfire only, today); inject a subset in tests.
        self._registry = dict(registry if registry is not None else default_registry())

    def sweep(self, cells: Sequence[WorldCellState]) -> dict[CellId, CellScores]:
        """Run every hazard's index over ``cells`` → ``{cell_id: {hazard: score}}``.

        Pure and vectorized: each index makes one array pass over the batch. A cell appears
        under a hazard only if that hazard could score it, so a hazard with no relevant state
        for a cell contributes nothing there — no crash, no fabricated number.
        """
        result: dict[CellId, CellScores] = {}
        for hazard, index in self._registry.items():
            for cell_id, score in index.score(cells).items():
                result.setdefault(cell_id, {})[hazard] = score
        return result

    def sweep_store(self, store: ActiveCellStore) -> dict[CellId, CellScores]:
        """Pull the store's active states in one pass and sweep them — never the whole grid,
        and with no recency side effect on the store."""
        return self.sweep(store.active_states())


def demo() -> None:
    """Self-check: sweeping a mixed active set screens the wildfire cells and skips the rest."""
    from vectis.realtime.state.store import MemoryStateStore

    store: MemoryStateStore[WorldCellState] = MemoryStateStore()
    store.save_state(WorldCellState(cell_id="hot", temperature=33.0, extra={"wind_speed_kmh": 40.0}))
    store.save_state(WorldCellState(cell_id="cyclone", extra={"cyclone_alert_level": 3.0}))

    scores = GlobalScreeningSweep().sweep_store(store)
    assert "wildfire" in scores["hot"], scores
    assert "cyclone" not in scores, "a cyclone-only cell has no wildfire state to screen"
    print("OK", {c: {h: round(s.value, 1) for h, s in hz.items()} for c, hz in scores.items()})


if __name__ == "__main__":
    demo()
