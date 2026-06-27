"""Tests for the Session-10 Digital Twin foundation (Climate Risk / RegionTwin).

Covers the brief's three behaviors plus the registry and the streaming wiring:
- a fresh twin has its default state and an already-computed risk picture,
- a deterministic transition (high temperature) raises vegetation stress,
- an observation updates the twin's physical state *and* triggers a risk recompute,
- the StateManager registry, and an event routed end-to-end into the twin.
"""

from __future__ import annotations

from vectis.digital_twin.entities.region import RegionState, RegionTwin
from vectis.digital_twin.state.manager import StateManager
from vectis.digital_twin.transitions.base import ClimateTransition
from vectis.simulation.probability.bayesian import Observation
from vectis.streaming.events import WeatherAlert
from vectis.streaming.updater import build_default_updater


# ── Initialization / default state ───────────────────────────────────────────
def test_twin_initializes_with_default_state():
    twin = RegionTwin("liguria")
    state = twin.get_current_state()
    assert isinstance(state, RegionState)
    assert state.temperature_anomaly == 2.0
    assert state.humidity_level == 20.0
    assert state.vegetation_stress == 50.0
    assert state.recent_fire_history == 0.0

    # Risk is computed at construction (baseline run), priors at generator defaults.
    risk = twin.computed_risk_state
    assert risk.region == "liguria"
    assert 0.0 <= risk.risk <= 100.0
    assert risk.scenario_priors["hotter_drier"] == 0.3


# ── Deterministic transition ─────────────────────────────────────────────────
def test_high_temperature_increases_vegetation_stress():
    state = RegionState()
    changed = ClimateTransition().apply(state, Observation(variable="temp_anomaly_c", value=10.0))
    assert changed
    assert state.temperature_anomaly == 10.0
    assert state.vegetation_stress > 50.0  # heat dried the fuel out


def test_rain_raises_humidity_and_relieves_stress():
    state = RegionState(temperature_anomaly=2.0, vegetation_stress=60.0)
    changed = ClimateTransition().apply(state, Observation(variable="rainfall_mm", value=40.0))
    assert changed
    assert state.humidity_level == 60.0  # 20 + 40 mm
    assert state.vegetation_stress < 60.0  # moisture relieved the stress


def test_unrelated_observation_does_not_drift_stress():
    # A fire detection accumulates history but must not silently move veg stress.
    state = RegionState()
    before = state.vegetation_stress
    ClimateTransition().apply(state, Observation(variable="active_fires", value=2.0))
    assert state.recent_fire_history == 2.0
    assert state.vegetation_stress == before


# ── Observation updates state AND triggers risk calculation ──────────────────
def test_observation_updates_state_and_recomputes_risk():
    twin = RegionTwin("liguria")
    before = twin.computed_risk_state

    update = twin.update_from_observation(
        Observation(variable="temp_anomaly_c", value=4.0, std=0.3)
    )

    # Physical state evolved deterministically.
    state = twin.get_current_state()
    assert state.temperature_anomaly == 4.0
    assert state.vegetation_stress > 50.0

    # Beliefs shifted toward the hotter/drier future and risk was recomputed.
    assert update.recomputed
    assert update.belief_shift > 0.0
    assert update.risk_state.scenario_priors["hotter_drier"] > 0.3
    assert update.risk_state.confidence > before.confidence
    assert update.risk_state.risk > before.risk  # hotter present + hotter belief


# ── Registry ─────────────────────────────────────────────────────────────────
def test_state_manager_registers_and_retrieves_twins():
    manager = StateManager()
    twin = RegionTwin("liguria")
    manager.register(twin)
    assert manager.count == 1
    assert manager.get("liguria") is twin
    assert manager.get("atlantis") is None

    manager.deregister("liguria")
    assert manager.count == 0


# ── Streaming wiring (event → twin) ──────────────────────────────────────────
def test_weather_alert_routes_into_the_twin():
    updater = build_default_updater()
    before = updater.risk_state("liguria")

    change = updater.process(
        WeatherAlert(source="arpal", region="liguria", variable="temp_anomaly_c",
                     value=4.0, severity="critical")
    )

    assert change is not None
    assert change.risk.region == "liguria"
    assert change.risk.scenario_priors["hotter_drier"] > 0.3
    # The manager's twin now reflects the alert.
    twin = updater.manager.get("liguria")
    assert twin.get_current_state().temperature_anomaly == 4.0
    assert before is not None and change.risk.risk >= before.risk
