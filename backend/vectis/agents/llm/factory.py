"""LLM provider factory — selects the provider from settings."""

from __future__ import annotations

from vectis.agents.llm.base import LLMProvider
from vectis.agents.llm.mock import MockProvider
from vectis.core.config import get_settings
from vectis.core.logging import get_logger

log = get_logger(__name__)


def get_llm_provider() -> LLMProvider:
    """Return the configured LLM provider (defaults to deterministic mock)."""
    provider = get_settings().llm_provider
    if provider == "claude":
        from vectis.agents.llm.anthropic import AnthropicProvider

        return AnthropicProvider()
    if provider != "mock":  # pragma: no cover - guarded by Settings Literal
        log.warning("llm.unknown_provider", provider=provider)
    return MockProvider()
