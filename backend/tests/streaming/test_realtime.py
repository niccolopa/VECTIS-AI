"""Tests for the Session-9 real-time intelligence layer.

Covers the contract the streaming layer promises:
- ingestion returns **202 immediately** (never blocked by the simulation),
- the background task actually runs the **Bayesian update** (beliefs move),
- **debouncing** stops duplicate measurements from re-updating,
- the **WebSocket broadcaster** connect/broadcast/disconnect logic, and an
  end-to-end ingest→broadcast push.
"""

from __future__ import annotations

import asyncio

from vectis.streaming.broadcaster import ConnectionManager
from vectis.streaming.events import SensorReading
from vectis.streaming.updater import build_default_updater


def _strong_hotter_event(value: float = 4.0) -> dict:
    # Above the +2.0 °C estimate → evidence for the "hotter_drier" branch.
    return {
        "kind": "sensor_reading",
        "source": "station-genova",
        "variable": "temp_anomaly_c",
        "value": value,
        "std": 0.3,
    }


# ── Ingestion is async (202, non-blocking) ───────────────────────────────────
def test_ingest_returns_202_immediately(client):
    res = client.post("/api/v1/stream/ingest", json=_strong_hotter_event())
    assert res.status_code == 202
    body = res.json()
    assert body["status"] == "accepted"
    assert body["event_id"]  # server-assigned id echoed back


# ── Background task runs the Bayesian update ─────────────────────────────────
def test_ingest_triggers_bayesian_update(client):
    before = client.get("/api/v1/stream/state").json()
    assert before["scenario_priors"]["hotter_drier"] == 0.3  # prior baseline

    # TestClient runs background tasks before the POST call returns.
    client.post("/api/v1/stream/ingest", json=_strong_hotter_event())

    after = client.get("/api/v1/stream/state").json()
    assert after["scenario_priors"]["hotter_drier"] > before["scenario_priors"]["hotter_drier"]
    assert after["confidence"] > before["confidence"]  # belief sharpened


def test_duplicate_events_are_debounced(client):
    event = _strong_hotter_event()
    client.post("/api/v1/stream/ingest", json=event)
    first = client.get("/api/v1/stream/state").json()

    # Same source/variable/value within the debounce window → dropped, beliefs frozen.
    client.post("/api/v1/stream/ingest", json=event)
    second = client.get("/api/v1/stream/state").json()
    assert second["scenario_priors"] == first["scenario_priors"]


# ── WebSocket broadcaster (unit) ─────────────────────────────────────────────
class _FakeWS:
    def __init__(self, fail: bool = False) -> None:
        self.accepted = False
        self.sent: list[dict] = []
        self._fail = fail

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, data: dict) -> None:
        if self._fail:
            raise RuntimeError("peer gone")
        self.sent.append(data)


def test_connection_manager_connect_and_broadcast():
    async def scenario() -> None:
        mgr = ConnectionManager()
        a, b = _FakeWS(), _FakeWS()
        await mgr.connect(a)
        await mgr.connect(b)
        assert mgr.count == 2 and a.accepted and b.accepted

        delivered = await mgr.broadcast({"type": "state_changed", "risk": 42})
        assert delivered == 2
        assert a.sent[-1]["risk"] == 42 and b.sent[-1]["risk"] == 42

        mgr.disconnect(a)
        assert mgr.count == 1

    asyncio.run(scenario())


def test_broadcast_drops_dead_connections():
    async def scenario() -> None:
        mgr = ConnectionManager()
        good, dead = _FakeWS(), _FakeWS(fail=True)
        await mgr.connect(good)
        await mgr.connect(dead)

        delivered = await mgr.broadcast({"type": "state_changed"})
        assert delivered == 1  # only the healthy peer
        assert mgr.count == 1  # dead one was pruned

    asyncio.run(scenario())


# ── End-to-end ingest → WebSocket push ───────────────────────────────────────
def test_ingest_broadcasts_to_connected_websocket(client):
    with client.websocket_connect("/api/v1/stream/ws") as ws:
        client.post("/api/v1/stream/ingest", json=_strong_hotter_event(value=4.5))
        message = ws.receive_json()
        assert message["type"] == "state_changed"
        assert message["risk"]["region"] == "california"
        assert 0.0 <= message["risk"]["confidence"] <= 1.0


# ── Pure-orchestrator seam (no HTTP, no LLM) ─────────────────────────────────
def test_process_is_callable_without_http():
    updater = build_default_updater()
    change = updater.process(
        SensorReading(source="probe", variable="temp_anomaly_c", value=4.0, std=0.3)
    )
    assert change is not None
    assert change.triggered_rerun in (True, False)
    assert change.risk.scenario_priors["hotter_drier"] > 0.3
