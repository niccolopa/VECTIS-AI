"""Shared test configuration and fixtures.

Tests run fully offline: the LLM provider is forced to ``mock`` and the database
to a temporary SQLite file. Sample data is generated and a model trained once
per session into a temp artifacts dir, so the suite is self-contained and
deterministic.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

# Configure the environment BEFORE importing any vectis module that reads settings.
_TMP = Path(tempfile.mkdtemp(prefix="vectis-test-"))
os.environ.update(
    {
        "VECTIS_ENV": "test",
        "VECTIS_LLM_PROVIDER": "mock",
        "VECTIS_DATABASE_URL": f"sqlite:///{(_TMP / 'test.db').as_posix()}",
        "VECTIS_DATA_DIR": str(_TMP / "data"),
        "VECTIS_ARTIFACTS_DIR": str(_TMP / "artifacts"),
        "VECTIS_RANDOM_SEED": "42",
        # Keep the global ingestion loop parked: it writes real worldwide events into
        # the same tile_store the API tests seed with known cells. Tests that need
        # ticks drive GlobalIngestionBroadcaster.poll_once() deterministically.
        "VECTIS_GLOBAL_INGESTION": "0",
    }
)

from vectis.core.config import get_settings  # noqa: E402

get_settings.cache_clear()


@pytest.fixture(scope="session", autouse=True)
def _prepare_environment() -> None:
    """Seed sample data and train a model once for the whole session."""
    from vectis.scripts.generate_sample import generate
    from vectis.scripts.train import train_region

    generate()
    train_region("california")


@pytest.fixture
def client():
    """A FastAPI TestClient with lifespan (service/repository) initialized."""
    from fastapi.testclient import TestClient

    from vectis.api.main import create_app

    with TestClient(create_app()) as c:
        yield c


@pytest.fixture
def pipeline_result():
    """A fresh labeled pipeline result for the sample region."""
    from vectis.data.connectors import get_connector
    from vectis.data.pipeline.runner import run_pipeline
    from vectis.data.regions import get_region

    raw = get_connector("sample").fetch(get_region("california"))
    return run_pipeline(raw, require_label=True)
