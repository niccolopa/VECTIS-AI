"""The Sluice — VECTIS's optional outbound feed gateway.

A *sluice* is a gate on a channel: it holds back the flow, smooths it, and — with more
than one gate — keeps water moving when any single gate jams. That is exactly this
service's job, and nothing more:

1. **Hold outbound credentials** for the one upstream that needs one (NASA FIRMS). USGS
   and GDACS are keyless and pass straight through.
2. **Retry / normalize** each upstream call so a transient outage or a flaky key becomes
   a clean, consistently-shaped response instead of a connector-side crash.
3. **Fail over** across multiple credentials for the *same* source: if the first FIRMS
   key is jammed (invalid, throttled, or the request errored), try the next one, so one
   bad key never takes the fire feed down.

**It exists purely for reliability.** It is a small, standalone service VECTIS owns end to
end — not modeled on any third-party product. It mirrors each upstream's exact path shape,
so a connector builds the *same* URL whether it points at the Sluice or straight at the
real API: the Sluice is a drop-in, and every connector falls back to calling the upstream
directly when the Sluice isn't running. The project's offline/keyless promise is unbroken.

PROJECT PRINCIPLE — the Sluice is **not** a way to mass-register keys to get around any
provider's rate limits. Failover is for *outage tolerance* (one flaky key/transient fault
shouldn't kill a feed), never for pooling many keys to exceed a quota. Configure only keys
you are entitled to use, one primary + a spare or two.

Run it standalone (optional infra)::

    uvicorn vectis.ingress.sluice:app --port 8900
    # then point the connectors at it:
    export VECTIS_FIRMS_BASE_URL=http://localhost:8900
    export VECTIS_USGS_BASE_URL=http://localhost:8900
    export VECTIS_GDACS_BASE_URL=http://localhost:8900
"""

from __future__ import annotations

import time
from collections.abc import Callable

import httpx
from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse, PlainTextResponse

from vectis.core.config import get_settings
from vectis.core.logging import get_logger

logger = get_logger(__name__)

# Transport faults worth a same-target retry (a flaky link recovers; a 4xx does not).
_RETRYABLE = (httpx.TimeoutException, httpx.TransportError)


class SluiceError(RuntimeError):
    """Every upstream attempt (and every credential) was exhausted."""


class Sluice:
    """Forward one request per upstream source, with retry, normalization, and — for FIRMS
    only — credential failover. Framework-free so the failover logic is unit-testable
    without spinning up the HTTP app; the FastAPI routes below are thin wrappers over it.
    """

    def __init__(
        self,
        *,
        firms_keys: list[str] | None = None,
        firms_base: str = "https://firms.modaps.eosdis.nasa.gov",
        usgs_base: str = "https://earthquake.usgs.gov",
        gdacs_base: str = "https://www.gdacs.org",
        client: httpx.Client | None = None,
        max_retries: int = 3,
        backoff_base: float = 0.5,
        timeout: float = 15.0,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._firms_keys = [k for k in (firms_keys or []) if k]
        self._firms_base = firms_base.rstrip("/")
        self._usgs_base = usgs_base.rstrip("/")
        self._gdacs_base = gdacs_base.rstrip("/")
        self._client = client or httpx.Client(timeout=timeout)
        self._max_retries = max_retries
        self._backoff_base = backoff_base
        self._sleep = sleep

    # ----- resilient GET (retry a single target) --------------------------------

    def _get(self, url: str) -> httpx.Response:
        """GET ``url`` with exponential backoff. Retries timeouts/5xx, fails fast on 4xx."""
        last: Exception | None = None
        for attempt in range(self._max_retries):
            try:
                resp = self._client.get(url)
                if resp.status_code >= 500:
                    raise httpx.HTTPStatusError(
                        f"{resp.status_code}", request=resp.request, response=resp
                    )
                resp.raise_for_status()
                return resp
            except httpx.HTTPStatusError as exc:
                if exc.response is not None and exc.response.status_code < 500:
                    raise  # client error — a retry won't fix a bad request
                last = exc
            except _RETRYABLE as exc:
                last = exc
            if attempt + 1 < self._max_retries:
                self._sleep(self._backoff_base * (2**attempt))
        raise SluiceError(f"upstream unreachable after {self._max_retries} attempts: {last}")

    # ----- one method per upstream source ---------------------------------------

    def firms_area_csv(self, product: str, area: str, day_range: str) -> str:
        """FIRMS active-fire area CSV. Injects a held MAP_KEY and fails over across the pool.

        The path key the caller sent is ignored — the Sluice supplies the credential. Each
        key gets the full retry budget; a jammed key (network fault or a FIRMS ``Invalid
        MAP_KEY`` body) drops through to the next. Reliability, not quota-pooling.
        """
        if not self._firms_keys:
            raise SluiceError("Sluice holds no FIRMS MAP_KEY (set VECTIS_SLUICE_FIRMS_KEYS)")
        errors: list[str] = []
        for i, key in enumerate(self._firms_keys):
            url = f"{self._firms_base}/api/area/csv/{key}/{product}/{area}/{day_range}"
            try:
                body = self._get(url).text
            except SluiceError as exc:
                errors.append(f"key#{i}: {exc}")
                continue
            if _looks_like_firms_error(body):
                errors.append(f"key#{i}: rejected by FIRMS")
                logger.warning("[WARN] Sluice FIRMS key#%d jammed — failing over", i)
                continue
            return body
        raise SluiceError("all FIRMS credentials exhausted: " + "; ".join(errors))

    def usgs_summary(self, feed: str) -> object:
        """USGS earthquake summary GeoJSON (keyless pass-through)."""
        return self._get(
            f"{self._usgs_base}/earthquakes/feed/v1.0/summary/{feed}.geojson"
        ).json()

    def gdacs_events(self, profile: str) -> object:
        """GDACS multi-hazard event list GeoJSON (keyless pass-through)."""
        return self._get(
            f"{self._gdacs_base}/gdacsapi/api/events/geteventlist/{profile}"
        ).json()

    def close(self) -> None:
        self._client.close()


def _looks_like_firms_error(body: str) -> bool:
    """FIRMS answers a bad/over-quota key with 200 + a plaintext error, not a CSV header."""
    head = body.lstrip()[:200].lower()
    return "invalid map_key" in head or head.startswith("invalid")


def _build_sluice() -> Sluice:
    s = get_settings()
    raw = s.sluice_firms_keys or s.firms_api_key
    keys = [k.strip() for k in raw.split(",") if k.strip()]
    return Sluice(
        firms_keys=keys,
        firms_base=s.firms_base_url,
        usgs_base=s.usgs_base_url,
        gdacs_base=s.gdacs_base_url,
    )


def create_app(sluice: Sluice | None = None) -> FastAPI:
    """The standalone Sluice service — one endpoint per upstream, each mirroring the real
    API's path shape so a connector's URL is identical whether it targets the Sluice or the
    upstream. ``sluice`` is injectable for tests (drive it with an ``httpx.MockTransport``)."""
    app = FastAPI(
        title="VECTIS Sluice",
        version="1.0.0",
        summary="Optional outbound feed gateway — credential failover, retry, normalization.",
    )
    app.state.sluice = sluice or _build_sluice()

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "sluice"}

    # FIRMS — mirrors the real area-CSV path; the {map_key} segment is accepted for shape
    # parity but ignored (the Sluice injects its own held key).
    @app.get("/api/area/csv/{map_key}/{product}/{area}/{day_range}")
    def firms(map_key: str, product: str, area: str, day_range: str) -> Response:
        try:
            csv = app.state.sluice.firms_area_csv(product, area, day_range)
        except SluiceError as exc:
            return JSONResponse(status_code=502, content={"error": str(exc)})
        return PlainTextResponse(csv, media_type="text/csv")

    @app.get("/earthquakes/feed/v1.0/summary/{feed}.geojson")
    def usgs(feed: str) -> Response:
        try:
            return JSONResponse(content=app.state.sluice.usgs_summary(feed))
        except SluiceError as exc:
            return JSONResponse(status_code=502, content={"error": str(exc)})

    @app.get("/gdacsapi/api/events/geteventlist/{profile}")
    def gdacs(profile: str) -> Response:
        try:
            return JSONResponse(content=app.state.sluice.gdacs_events(profile))
        except SluiceError as exc:
            return JSONResponse(status_code=502, content={"error": str(exc)})

    return app


app = create_app()
