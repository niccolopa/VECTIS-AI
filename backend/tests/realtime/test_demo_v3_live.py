"""The V3 live demo must produce a *living* stream, not a static report.

One headless run asserts the system actually evolves: as the mock feeds get hotter
and drier, risk climbs, the scenario belief swings toward ``hotter_drier``, and the
decision board re-convenes when risk moves materially.
"""

from __future__ import annotations

import asyncio
import io

from vectis.scripts.demo_v3_live import run_live


def _run(ticks: int) -> list:
    return asyncio.run(
        run_live(ticks=ticks, tick_seconds=0.0, n_iterations=2_000, color=False, out=io.StringIO())
    )


def test_stream_is_alive() -> None:
    frames = _run(11)
    assert len(frames) == 11

    # Risk rises monotonically-ish and ends materially higher than it began.
    assert frames[-1].risk > frames[0].risk + 5.0

    # The belief swings from baseline toward hotter_drier as the heat/drought build.
    assert frames[0].posterior["hotter_drier"] < 0.05
    assert frames[-1].posterior["hotter_drier"] > 0.5
    assert frames[-1].driver != frames[0].driver  # primary driver label flips

    # Kalman variance shrinks as corroborating data accumulates (more confident state).
    assert frames[-1].temp_var < frames[0].temp_var

    # The board re-convenes at least once on a material risk move.
    assert any(f.report_id for f in frames)


if __name__ == "__main__":
    test_stream_is_alive()
    print("ok")
