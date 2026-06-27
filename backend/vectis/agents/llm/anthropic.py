"""Anthropic Claude provider.

Narrates findings using Claude when ``VECTIS_LLM_PROVIDER=claude`` and an API key
is set. The ``anthropic`` SDK is an optional dependency (``pip install -e
'.[llm]'``); import is lazy so the default install stays lean. Any failure
degrades gracefully to the deterministic fallback, preserving availability.
"""

from __future__ import annotations

import json
from typing import Any

from vectis.agents.llm.base import LLMProvider, NarrationResult
from vectis.core.config import get_settings
from vectis.core.logging import get_logger

log = get_logger(__name__)

_SYSTEM = (
    "You are a domain analyst writing one section of a decision-intelligence "
    "report. You will be given an instruction and a JSON context of already-"
    "computed facts (scores, drivers, metrics). Rephrase ONLY these facts into "
    "clear, precise, non-alarmist prose. Do not invent numbers, claims, or "
    "recommendations beyond the context. Be concise."
)


class AnthropicProvider(LLMProvider):
    name = "claude"

    def __init__(self) -> None:
        self._settings = get_settings()
        self._client = None  # lazily created on first use

    def _get_client(self) -> Any:
        if self._client is None:
            from anthropic import Anthropic  # lazy import (optional dep)

            self._client = Anthropic(api_key=self._settings.anthropic_api_key)
        return self._client

    def narrate(self, *, instruction: str, context: dict[str, Any], fallback: str,
                max_tokens: int = 600) -> NarrationResult:
        if not self._settings.anthropic_api_key:
            log.warning("llm.no_api_key", provider=self.name)
            return NarrationResult(text=fallback, used_llm=False)
        try:
            client = self._get_client()
            message = client.messages.create(
                model=self._settings.llm_model,
                max_tokens=max_tokens,
                system=_SYSTEM,
                messages=[{
                    "role": "user",
                    "content": f"Instruction: {instruction}\n\nContext (JSON):\n"
                               f"{json.dumps(context, default=str, indent=2)}",
                }],
            )
            text = "".join(block.text for block in message.content
                           if getattr(block, "type", None) == "text").strip()
            return NarrationResult(text=text or fallback, used_llm=bool(text))
        except Exception as exc:  # degrade gracefully — availability over polish
            log.warning("llm.narrate_failed", provider=self.name, error=str(exc))
            return NarrationResult(text=fallback, used_llm=False)
