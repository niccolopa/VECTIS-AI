"""Dashboard API tests (Session 14).

Exercise the two endpoints the V2 frontend depends on: the twin view (state +
RiskState + per-scenario distributions + AI report) and the What-If simulator.
Also assert the payloads carry enough statistics to draw a box-and-whisker chart
(p05/p50/p95), which is the session's enterprise-UX requirement.
"""

from __future__ import annotations


def test_list_twins_includes_california(client) -> None:
    res = client.get("/api/v1/dashboard/twins")
    assert res.status_code == 200
    assert "california" in res.json()


def test_twin_view_shape(client) -> None:
    res = client.get("/api/v1/dashboard/twins/california")
    assert res.status_code == 200
    body = res.json()

    # Aggregate risk with the statistics an enterprise UI needs.
    risk = body["risk"]
    assert 0.0 <= risk["risk"] <= 100.0
    assert 0.0 <= risk["confidence"] <= 1.0
    assert risk["band"] in {"low", "moderate", "high", "severe"}
    assert risk["scenario_priors"]  # weights per branch

    # Per-scenario distributions — box-and-whisker ready (p05 <= p50 <= p95).
    assert len(body["scenarios"]) == 3
    for s in body["scenarios"]:
        d = s["risk"]
        assert d["p05"] <= d["p50"] <= d["p95"]
        assert "exceedance" in d  # tail probabilities for fan/threshold charts
        assert 0.0 <= s["probability"] <= 1.0

    # The AI brief is embedded and structured (not a wall of text).
    report = body["report"]
    assert report["bottom_line"]
    assert report["analyst"]["risk_band"] == risk["band"]
    assert report["debate"]["optimist_case"] and report["debate"]["pessimist_case"]
    assert report["red_team"]["challenge"]


def test_twin_view_unknown_returns_404(client) -> None:
    assert client.get("/api/v1/dashboard/twins/atlantis").status_code == 404


def test_what_if_hotter_raises_risk(client) -> None:
    baseline = client.get("/api/v1/dashboard/twins/california").json()["risk"]["risk"]

    res = client.post(
        "/api/v1/dashboard/simulate/what-if",
        json={"twin_id": "california", "overrides": {"temperature_anomaly": 5.0}},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["state"]["temperature_anomaly"] == 5.0
    assert 0.0 <= body["risk"]["risk"] <= 100.0
    assert len(body["scenarios"]) == 3
    # Sliding temperature up must not lower the risk (sanity on the mapping).
    assert body["risk"]["risk"] >= baseline


def test_what_if_is_deterministic_and_cached(client) -> None:
    payload = {"twin_id": "california", "overrides": {"vegetation_stress": 80.0}}
    first = client.post("/api/v1/dashboard/simulate/what-if", json=payload).json()
    second = client.post("/api/v1/dashboard/simulate/what-if", json=payload).json()
    # Same inputs ⇒ identical numbers (seeded engine + S13 cache).
    assert first["risk"]["risk"] == second["risk"]["risk"]
    assert first["scenarios"][0]["risk"]["p50"] == second["scenarios"][0]["risk"]["p50"]


def test_what_if_unknown_twin_returns_404(client) -> None:
    res = client.post(
        "/api/v1/dashboard/simulate/what-if", json={"twin_id": "atlantis", "overrides": {}}
    )
    assert res.status_code == 404
