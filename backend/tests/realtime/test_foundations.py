"""V3 foundation contracts (Session 16 blueprint).

These guard the *interfaces*, not behavior (there is no filter logic yet): the global
event schema enforces its trust-boundary validation, and the StateEstimator ABC is
shaped for continuous, per-cell streaming and can be implemented.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from vectis.realtime.events import GeoPoint, GlobalEvent, GlobalObservation
from vectis.realtime.state import CellState, StateEstimator


def test_global_event_carries_geospatial_scope() -> None:
    evt = GlobalEvent(source="nasa_firms", location=GeoPoint(lat=44.4, lon=8.9))
    assert evt.cell_id is None  # assigned later by a processor
    assert evt.event_id and evt.observed_at <= datetime.now(UTC)
    with pytest.raises(NotImplementedError):
        evt.to_observation()  # base hook; concrete sources implement it


def test_geopoint_rejects_out_of_range_coordinates() -> None:
    GeoPoint(lat=-90, lon=180)  # bounds are inclusive
    with pytest.raises(ValidationError):
        GeoPoint(lat=91, lon=0)
    with pytest.raises(ValidationError):
        GeoPoint(lat=0, lon=-181)


def test_state_estimator_is_abstract_and_streamable() -> None:
    # The ABC cannot be instantiated directly...
    with pytest.raises(TypeError):
        StateEstimator()  # type: ignore[abstract]

    # ...and a minimal concrete estimator satisfies the continuous-stream contract.
    class DictEstimator(StateEstimator):
        def __init__(self) -> None:
            self._cells: dict[str, CellState] = {}

        def update(self, observation: GlobalObservation) -> CellState:
            state = self._cells.setdefault(observation.cell_id, CellState(cell=observation.cell_id))
            state.mean[observation.variable] = observation.value
            return state

        def predict(self, cell: str, at: datetime) -> CellState | None:
            return self._cells.get(cell)

        def get(self, cell: str) -> CellState | None:
            return self._cells.get(cell)

        @property
        def active_cells(self) -> int:
            return len(self._cells)

    est = DictEstimator()
    obs = [
        GlobalObservation(cell_id="cellA", variable="temp_anomaly_c", value=4.0, source="s"),
        GlobalObservation(cell_id="cellB", variable="temp_anomaly_c", value=1.0, source="s"),
    ]
    results = est.update_batch(obs)  # default batch loops update()
    assert len(results) == 2
    assert est.active_cells == 2
    assert est.get("cellA").mean["temp_anomaly_c"] == 4.0
