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
