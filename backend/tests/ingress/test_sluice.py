"""Sluice gateway — credential failover, keyless pass-through, and total-outage handling.

Drives the HTTP layer with an ``httpx.MockTransport`` (no sockets) and a no-op sleep so
backoff doesn't wait. Failover is the one piece of real logic here, so it gets the coverage.
"""

from __future__ import annotations

import httpx
import pytest

from vectis.ingress.sluice import Sluice, SluiceError


def _sluice(handler, **kw) -> Sluice:
    client = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://test")
    return Sluice(client=client, sleep=lambda _: None, **kw)


def test_firms_fails_over_from_a_jammed_key_to_a_working_one() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        # The bad key gets FIRMS's 200-with-plaintext-error; the good one gets a CSV.
        if "/BADKEY/" in request.url.path:
            return httpx.Response(200, text="Invalid MAP_KEY.")
        return httpx.Response(200, text="latitude,longitude,frp\n37.0,-120.0,12.4\n")

    sluice = _sluice(handler, firms_keys=["BADKEY", "GOODKEY"], firms_base="http://test")
    csv = sluice.firms_area_csv("VIIRS_SNPP_NRT", "-124,32,-114,42", "1")

    assert "37.0,-120.0,12.4" in csv  # served by the second key after failover


def test_firms_raises_when_every_credential_is_exhausted() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="Invalid MAP_KEY.")

    sluice = _sluice(handler, firms_keys=["K1", "K2"], firms_base="http://test")
    with pytest.raises(SluiceError):
        sluice.firms_area_csv("P", "A", "1")


def test_firms_without_any_key_is_a_clean_error() -> None:
    sluice = _sluice(lambda r: httpx.Response(200), firms_keys=[], firms_base="http://test")
    with pytest.raises(SluiceError):
        sluice.firms_area_csv("P", "A", "1")


def test_usgs_passes_through_keyless() -> None:
    body = {"type": "FeatureCollection", "features": []}
    sluice = _sluice(lambda r: httpx.Response(200, json=body), usgs_base="http://test")
    assert sluice.usgs_summary("4.5_day") == body


def test_transient_5xx_is_retried_then_succeeds() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(503)
        return httpx.Response(200, json={"ok": True})

    sluice = _sluice(handler, gdacs_base="http://test")
    assert sluice.gdacs_events("MAP") == {"ok": True}
    assert calls["n"] == 2  # one retry after the 503
