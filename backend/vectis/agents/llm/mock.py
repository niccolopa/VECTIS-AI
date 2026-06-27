"""Deterministic mock provider — the default.

Returns the agent's deterministic fallback narration verbatim. This is what
makes VECTIS reproducible and runnable in CI/demos with no API key: every run
produces byte-identical reports.
"""

from __future__ import annotations

from typing import Any

from vectis.agents.llm.base import LLMProvider, NarrationResult


class MockProvider(LLMProvider):
    name = "mock"

    def narrate(self, *, instruction: str, context: dict[str, Any], fallback: str,
                max_tokens: int = 600) -> NarrationResult:  # noqa: ARG002
        return NarrationResult(text=fallback, used_llm=False)
