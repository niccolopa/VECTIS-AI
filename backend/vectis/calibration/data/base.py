"""Shared plumbing for the archive clients: the error type and resilient HTTP.

:class:`ArchiveHttp` reuses the Session-17 :class:`BaseAPIConnector` retry/backoff
machinery (timeouts and 5xx retried with exponential backoff, 4xx fails fast, injectable
``httpx`` client for offline tests). The event-stream half of that contract
(``fetch``/``normalize``) is deliberately unused — an archive pull is an explicit,
parameterized batch request, not a polling feed — so those methods raise if called.

Unlike the live connectors, archive clients have **no offline fallback**: calibration
data must be real or absent, never fabricated. A missing credential or dead network
raises :class:`CalibrationDataError` with instructions instead of degrading.
"""

from __future__ import annotations

from typing import Any

from vectis.realtime.connectors.base import BaseAPIConnector
from vectis.realtime.events.base import GlobalEvent


class CalibrationDataError(RuntimeError):
    """A calibration fetch cannot proceed (missing credential, unreachable archive)."""


class ArchiveHttp(BaseAPIConnector):
    """Resilient batch HTTP: the connector's retry engine without the feed contract."""

    source = "calibration_archive"

    def fetch(self) -> Any:
        raise NotImplementedError("archive clients pull explicit windows, not polls")

    def normalize(self, raw: Any) -> list[GlobalEvent]:
        raise NotImplementedError("archive rows are training data, never stream events")
