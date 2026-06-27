"""LLM provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class NarrationResult:
    """Result of a narration request."""

    text: str
    used_llm: bool


class LLMProvider(ABC):
    """Narrates structured findings into prose.

    Implementations must be safe to call without network access at construction
    time; only :meth:`narrate` may reach out, and it must fall back gracefully.
    """

    name: str = "provider"

    @abstractmethod
    def narrate(self, *, instruction: str, context: dict[str, Any], fallback: str,
                max_tokens: int = 600) -> NarrationResult:
        """Return prose for ``instruction`` given ``context``.

        ``fallback`` is a complete, deterministic rendering that MUST be returned
        if the LLM is unavailable or errors. This keeps the system functional and
        reproducible offline.
        """
        raise NotImplementedError
