"""Pluggable LLM provider layer.

The provider abstraction is deliberately narrow: agents ask the LLM to *narrate*
already-computed, structured findings, always supplying a deterministic
``fallback``. This guarantees VECTIS runs fully offline (the ``mock`` provider
returns the fallback verbatim) while allowing Claude to produce polished,
human-grade prose when configured. The LLM never invents the numbers — it only
phrases them — which keeps outputs explainable and reproducible.
"""

from vectis.agents.llm.base import LLMProvider, NarrationResult
from vectis.agents.llm.factory import get_llm_provider
from vectis.agents.llm.mock import MockProvider

__all__ = ["LLMProvider", "NarrationResult", "MockProvider", "get_llm_provider"]
