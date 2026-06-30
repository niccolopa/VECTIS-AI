"""The V3 live demo must produce a *living* stream, not a static report.

One headless run asserts the system actually evolves: as the fluctuating feeds rise and
fall around a fire-season baseline, risk moves up AND down (it does not ramp to a 100%
flatline), the Kalman state grows more confident as data accumulates, and the decision
board re-convenes when risk moves materially.
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

    # The fluctuating feeds make risk move up AND down — never a flatline at the ceiling.
    risks = [f.risk for f in frames]
    assert any(b > a + 0.5 for a, b in zip(risks, risks[1:], strict=False)), "risk never rises"
    assert any(b < a - 0.5 for a, b in zip(risks, risks[1:], strict=False)), "risk never falls (flatlining)"
    assert max(risks) - min(risks) > 5.0, "risk barely moves"

    # Kalman variance shrinks as corroborating data accumulates (more confident state).
    assert frames[-1].temp_var < frames[0].temp_var

    # The board re-convenes at least once on a material risk move.
    assert any(f.report_id for f in frames)


if __name__ == "__main__":
    test_stream_is_alive()
    print("ok")
