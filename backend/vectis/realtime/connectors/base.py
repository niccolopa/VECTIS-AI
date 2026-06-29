"""The resilient base API connector — V3's contract with an unreliable internet.

External feeds time out, drop connections, and return transient 5xx errors. The base
absorbs all of that *once* so concrete connectors stay tiny:

- :meth:`BaseAPIConnector.get_json` — one HTTP GET wrapped in **exponential backoff**.
  Retries timeouts, connection errors, and 5xx; gives up on 4xx (a client bug won't
  fix itself by retrying). Raises :class:`ConnectorError` only after exhausting retries.
- :meth:`BaseAPIConnector.collect` — ``fetch`` → ``normalize`` that **never raises**:
  on a total outage it logs once and returns ``[]``, so a dead feed degrades the
  ingestion stream instead of crashing it (the Session-17 resilience requirement).

Concrete connectors implement :meth:`fetch` (get the raw payload) and
:meth:`normalize` (raw → :class:`~vectis.realtime.events.base.GlobalEvent` list). The
HTTP client is injectable so tests drive it with an ``httpx.MockTransport`` — no real
sockets, no ``responses``/``requests-mock`` dependency.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

import httpx

from vectis.core.logging import get_logger
from vectis.realtime.events.base import GlobalEvent

logger = get_logger(__name__)

# Transport-level failures worth retrying: timeouts and connection drops. A flaky feed
# recovers; a malformed request (4xx) does not, so those are raised immediately.
_RETRYABLE_NETWORK = (httpx.TimeoutException, httpx.TransportError)


class ConnectorError(RuntimeError):
    """Raised when a connector exhausts its retries against an unhealthy feed."""


class BaseAPIConnector(ABC):
    """A resilient source of :class:`GlobalEvent`s backed by an external JSON API.

    Subclasses set :attr:`source`, implement :meth:`fetch` + :meth:`normalize`, and get
    retrying HTTP + graceful-degradation for free.
    """

    #: Stable feed id, carried into every event/observation for provenance.
    source: str = "base"

    def __init__(
        self,
        *,
        base_url: str | None = None,
        client: httpx.Client | None = None,
        max_retries: int = 3,
        backoff_base: float = 0.5,
        timeout: float = 10.0,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.base_url = base_url
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.timeout = timeout
        self._sleep = sleep  # injectable so tests don't actually wait on backoff
        self._client = client or httpx.Client(timeout=timeout)

    # ----- resilient HTTP -------------------------------------------------------

    def get_json(self, url: str, *, params: dict[str, Any] | None = None) -> Any:
        """GET ``url`` and return parsed JSON, retrying transient failures with backoff.

        Backoff is ``backoff_base * 2**attempt`` seconds. Timeouts, connection errors,
        and 5xx are retried; 4xx and JSON-decode errors fail fast. Raises
        :class:`ConnectorError` if every attempt fails.
        """
        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                response = self._client.get(url, params=params)
                if response.status_code >= 500:
                    # Server-side hiccup — treat like a transient network fault.
                    raise httpx.HTTPStatusError(
                        f"{response.status_code} from {url}",
                        request=response.request,
                        response=response,
                    )
                response.raise_for_status()  # 4xx -> raise, not retried
                return response.json()
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                if status < 500:
                    logger.error("[ERROR] %s rejected request (%s) — not retrying", self.source, status)
                    raise ConnectorError(f"{self.source}: client error {status}") from exc
                last_error = exc
            except _RETRYABLE_NETWORK as exc:
                last_error = exc

            wait = self.backoff_base * (2**attempt)
            logger.warning(
                "[WARN] %s fetch failed (attempt %d/%d): %s — backing off %.1fs",
                self.source, attempt + 1, self.max_retries, last_error, wait,
            )
            if attempt + 1 < self.max_retries:
                self._sleep(wait)

        raise ConnectorError(
            f"{self.source}: feed unreachable after {self.max_retries} attempts"
        ) from last_error

    # ----- the connector contract ----------------------------------------------

    @abstractmethod
    def fetch(self) -> Any:
        """Return the raw payload (parsed JSON) from the feed. Offline-safe in subclasses."""
        raise NotImplementedError

    @abstractmethod
    def normalize(self, raw: Any) -> list[GlobalEvent]:
        """Translate a raw payload into canonical :class:`GlobalEvent` objects."""
        raise NotImplementedError

    def collect(self) -> list[GlobalEvent]:
        """``fetch`` then ``normalize``, swallowing outages.

        The resilience seam: if the feed is down for five minutes this logs once per
        poll and returns ``[]`` — the ingestion stream stays alive and recovers
        automatically when the feed comes back.
        """
        logger.info("[INFO] Fetching %s data...", self.source)
        try:
            events = self.normalize(self.fetch())
        except ConnectorError as exc:
            logger.warning("[WARN] %s unavailable — skipping this cycle: %s", self.source, exc)
            return []
        logger.info("[INFO] %s yielded %d event(s)", self.source, len(events))
        return events

    def close(self) -> None:
        self._client.close()
