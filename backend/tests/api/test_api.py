"""API endpoint tests."""

from __future__ import annotations


def test_health(client) -> None:
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_readiness_reports_database(client) -> None:
    res = client.get("/health/ready")
    # Tests run against SQLite, so the DB check should pass and report ready.
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ready"
    assert body["checks"]["database"] == "ok"


def test_list_regions(client) -> None:
    res = client.get("/api/v1/regions")
    assert res.status_code == 200
    keys = [r["key"] for r in res.json()]
    assert "liguria" in keys


def test_run_and_fetch_analysis(client) -> None:
    created = client.post("/api/v1/analyses", json={"region": "liguria"})
    assert created.status_code == 201
    report = created.json()
    assert report["risk_score"] >= 0
    assert report["cell_risks"]

    fetched = client.get(f"/api/v1/analyses/{report['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == report["id"]


def test_unknown_region_returns_404(client) -> None:
    res = client.post("/api/v1/analyses", json={"region": "atlantis"})
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "region_not_found"


def test_model_card_endpoint(client) -> None:
    res = client.get("/api/v1/models/liguria")
    assert res.status_code == 200
    card = res.json()
    assert "metrics" in card and "feature_names" in card


def test_get_missing_analysis_returns_404(client) -> None:
    assert client.get("/api/v1/analyses/doesnotexist").status_code == 404
