"""The V3 live stream must emit JSON-serializable frames the SSE/UI layer can consume.

Asserts the frame contract (the fields the React console binds to), that the rolling
event feed carries normalized observations, and that a freshly-generated decision
report is attached exactly once (not re-sent every tick).
"""

from __future__ import annotations

import asyncio
import json

from vectis.realtime.live_stream import LiveClimateStream


def _frames(ticks: int) -> list[dict]:
    async def run() -> list[dict]:
        stream = LiveClimateStream(n_iterations=2_000)
        return [f async for f in stream.frames(ticks=ticks, tick_seconds=0.0)]

    return asyncio.run(run())


def test_frames_are_json_and_well_formed() -> None:
    frames = _frames(6)
    assert len(frames) == 6

    first = frames[0]
    # Every frame must round-trip through JSON for SSE.
    json.dumps(first)
    for key in ("tick", "cell", "cell_id", "risk", "band", "confidence", "driver",
                "posterior", "events", "temp_variance"):
        assert key in first

    # The event feed carries normalized observations (source + variable + value).
    assert first["events"], "frame should carry the events that drove it"
    ev = first["events"][0]
    assert {"source", "variable", "value"} <= ev.keys()

    # Posterior is a valid distribution.
    assert abs(sum(first["posterior"].values()) - 1.0) < 1e-6

    # prev_risk threads through: null on the first frame, the prior risk after.
    assert first["prev_risk"] is None
    assert frames[1]["prev_risk"] == first["risk"]


def test_risk_oscillates_and_does_not_flatline() -> None:
    """The live risk must move up AND down — the fluctuating feeds must not ramp to a flatline."""
    risks = [f["risk"] for f in _frames(24)]
    assert any(b > a + 0.5 for a, b in zip(risks, risks[1:], strict=False)), "risk never rises"
    assert any(b < a - 0.5 for a, b in zip(risks, risks[1:], strict=False)), "risk never falls (flatlining)"


def test_report_attached_once_when_board_convenes() -> None:
    frames = _frames(6)
    # The board re-convenes on a material move; the full report rides exactly the
    # frame it was generated on, never re-sent (report_id may persist; report is None).
    with_report = [f for f in frames if f["report"] is not None]
    assert with_report, "the board should convene at least once"
    report_ids = [f["report"]["report_id"] for f in with_report]
    assert len(report_ids) == len(set(report_ids))  # no duplicate full reports


if __name__ == "__main__":
    test_frames_are_json_and_well_formed()
    test_risk_oscillates_and_does_not_flatline()
    test_report_attached_once_when_board_convenes()
    print("ok")
