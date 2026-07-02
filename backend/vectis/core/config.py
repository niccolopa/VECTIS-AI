"""Centralized, environment-driven configuration.

All settings are read from environment variables prefixed ``VECTIS_`` (or a
``.env`` file). This is the single source of truth for runtime configuration —
nothing else in the codebase should read ``os.environ`` directly.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Repository layout anchors. config.py lives at backend/vectis/core/config.py, so
# the backend root is three parents up and the repo root is four.
_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_REPO_ROOT = _BACKEND_ROOT.parent


class Settings(BaseSettings):
    """Typed application settings, validated at startup."""

    model_config = SettingsConfigDict(
        env_prefix="VECTIS_",
        env_file=(".env", str(_REPO_ROOT / ".env")),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Application ---
    env: Literal["development", "production", "test"] = "development"
    log_level: str = "INFO"
    log_json: bool = False

    # --- API ---
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = "http://localhost:5173"

    # --- Database ---
    database_url: str = "postgresql+psycopg://vectis:vectis@db:5432/vectis"

    # --- LLM provider ---
    llm_provider: Literal["mock", "claude"] = "mock"
    anthropic_api_key: str = ""
    llm_model: str = "claude-opus-4-8"
    llm_fast_model: str = "claude-haiku-4-5"

    # --- Real-time connectors ---
    # NASA FIRMS "MAP_KEY" for the active-fire area API. Empty → the FIRMS connector
    # serves deterministic offline detections, so a fresh clone runs with no key.
    firms_api_key: str = ""

    # Per-source base URLs. Each defaults to the real upstream; point one at the optional
    # internal Sluice gateway (Step 1) instead and that source flows through it, with no
    # other code change. The Sluice mirrors each upstream's path shape, so a connector
    # builds the same URL either way — the Sluice is a drop-in, never a hard dependency.
    firms_base_url: str = "https://firms.modaps.eosdis.nasa.gov"
    usgs_base_url: str = "https://earthquake.usgs.gov"
    gdacs_base_url: str = "https://www.gdacs.org"

    # Historical ERA5 reanalysis for calibration (Session 34): Open-Meteo's keyless
    # archive API, which serves the Copernicus ERA5 dataset. Direct CDS access would
    # add VECTIS_CDS_API_KEY — see vectis/calibration/data/era5.py for the trade-off.
    era5_base_url: str = "https://archive-api.open-meteo.com"

    # Sluice-only: the FIRMS MAP_KEY pool the gateway holds and fails over across for
    # reliability (comma-separated). Empty → falls back to the single ``firms_api_key``.
    # NOT a rate-limit-evasion pool — see vectis/ingress/sluice.py.
    sluice_firms_keys: str = ""

    # --- Data / ML ---
    data_dir: Path = _REPO_ROOT / "data"
    artifacts_dir: Path = _BACKEND_ROOT / "artifacts"
    random_seed: int = 42

    # --- Agents ---
    critic_max_revisions: int = 1
    # Orchestration engine: 'custom' (default; deterministic, dependency-light) or
    # 'langgraph' (industry-standard graph runtime; requires the 'langgraph' extra).
    orchestrator: Literal["custom", "langgraph"] = "custom"

    @field_validator("cors_origins")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()

    @property
    def cors_origin_list(self) -> list[str]:
        """CORS origins as a list (comma-separated in the env var)."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def sample_dir(self) -> Path:
        """Directory holding bundled sample datasets."""
        return self.data_dir / "samples"

    @property
    def is_test(self) -> bool:
        return self.env == "test"


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings singleton."""
    return Settings()
