"""VECTIS V3 — live, continuous California wildfire risk stream.

Where ``demo_v2`` fires *one* shot through the pipeline, this drives the V3
:class:`~vectis.realtime.pipeline.ContinuousPipeline` as a **living system**: mock
weather + satellite feeds emit fresh JSON every tick (temperature, drought, and wind
fluctuating up and down around a fire-season baseline), the pipeline folds each reading
into its Kalman belief,
re-runs the Bayesian posterior, and — when the risk moves materially — convenes the
decision board. The terminal redraws a tactical console each tick so you watch the
risk *shift* in real time.

    IngestionManager(connectors)  →  EventProducer  →  broker
        →  ContinuousPipeline (Kalman → Bayesian → Monte Carlo → Decision Report)

Run it:  ``python -m vectis.scripts.demo_v3_live``   (Ctrl+C to stop; ``--ticks N`` to bound).

Offline and deterministic: no API key, no network. Every number comes from the
deterministic engines; the LLM (mock by default) only narrates — the Math Firewall holds.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass, field
from typing import TextIO

from vectis.agents.board.service import SimulationBoardService
from vectis.agents.llm.base import LLMProvider
from vectis.core.schemas import RiskBand
from vectis.realtime.state.cell_id import assign_cell_id
from vectis.realtime.forecasting.bayesian.priors import ScenarioPriors
from vectis.realtime.forecasting.bayesian.updater import ContinuousBayesianUpdater
from vectis.realtime.forecasting.kalman.state_model import KalmanCellState
from vectis.realtime.forecasting.kalman.updater import KalmanStateUpdater
from vectis.realtime.ingestion.manager import IngestionManager
from vectis.realtime.live_stream import (
    GlobalSatelliteConnector,
    OscillatingWeatherConnector,
)
from vectis.realtime.pipeline import (
    _DRIVER_LABELS,
    ContinuousPipeline,
    ForecastResult,
    default_scenario_profiles,
)
from vectis.realtime.state.store import MemoryStateStore
from vectis.realtime.streams.broker import DEFAULT_TOPIC, MemoryBroker
from vectis.realtime.streams.producer import EventProducer
from vectis.scripts.demo_v2 import (
    _BAND_COLOR,
    Console,
    _force_utf8_stdout,
    _silence_logs,
)
from vectis.simulation.engine.runner import VectorizedMonteCarloEngine
from vectis.simulation.scenarios.generator import (
    WildfireScenarioGenerator,
    california_wildfire_state,
)
from vectis.simulation.schemas import SimulationConfig

WIDTH = 76
CELL_LABEL = "California_01"  # friendly name for the grid cell the California feeds map to


@dataclass
class LiveFrame:
    """One tick's rendered state — returned so the loop is testable headlessly."""

    tick: int
    cell: str
    risk: float
    prev_risk: float | None
    band: RiskBand
    confidence: float
    temp_mean: float
    temp_var: float
    temp_delta: float
    driver: str
    posterior: dict[str, float]
    report_id: str | None = None


@dataclass
class _LivePipeline:
    """The wired pipeline plus the handles the renderer needs (Kalman store, producer)."""

    pipeline: ContinuousPipeline
    producer: EventProducer
    store: MemoryStateStore[KalmanCellState]
    cell_id: str
    burst: int = field(default=0)


def _build(*, n_iterations: int, seed: int, llm: LLMProvider | None) -> _LivePipeline:
    """Wire the live California pipeline, keeping the Kalman store so we can show variance.

    Mirrors ``build_default_pipeline`` but holds the store reference (and the producer)
    that the live console needs — the demo's bootstrap *is* the wiring.
    """
    store: MemoryStateStore[KalmanCellState] = MemoryStateStore()
    kalman = KalmanStateUpdater(store)
    bayesian = ContinuousBayesianUpdater(
        default_scenario_profiles(),
        ScenarioPriors(
            {"baseline": 0.5, "hotter_drier": 0.3, "extreme_wind": 0.2},
            baseline={"baseline": 0.5, "hotter_drier": 0.3, "extreme_wind": 0.2},
            # >0 so the belief is never pinned at 0/100 — it can swing toward
            # hotter_drier as the heat/drought evidence mounts, then settle.
            relax_rate=0.4,
        ),
    )
    base_state = california_wildfire_state("california")
    scenarios = WildfireScenarioGenerator().generate(base_state)
    broker = MemoryBroker()
    pipeline = ContinuousPipeline(
        broker=broker,
        kalman=kalman,
        bayesian=bayesian,
        engine=VectorizedMonteCarloEngine(),
        board=SimulationBoardService(llm=llm),
        base_state=base_state,
        scenarios=scenarios,
        config=SimulationConfig(n_iterations=n_iterations, seed=seed),
        risk_change_threshold=2.0,
    )

    weather = OscillatingWeatherConnector()
    satellite = GlobalSatelliteConnector()
    manager = IngestionManager([weather, satellite])
    producer = EventProducer(manager, broker, topic=DEFAULT_TOPIC)
    # Both feeds report at California's centroid → the same grid cell.
    cell_id = assign_cell_id(weather.location.lat, weather.location.lon)
    return _LivePipeline(pipeline, producer, store, cell_id)


def _frame(lp: _LivePipeline, tick: int, prev: LiveFrame | None) -> LiveFrame | None:
    """Read the pipeline's latest output for the cell into a renderable frame."""
    result: ForecastResult | None = lp.pipeline.results.get(lp.cell_id)
    state = lp.store.get_state(lp.cell_id)
    if result is None or state is None:
        return None
    temp = state.estimates.get("temperature")
    temp_mean = temp.mean if temp else 0.0
    temp_var = temp.variance if temp else 0.0
    dominant = max(result.posterior, key=lambda k: result.posterior[k], default="baseline")
    return LiveFrame(
        tick=tick,
        cell=CELL_LABEL,
        risk=result.risk_score,
        prev_risk=prev.risk if prev else None,
        band=result.risk_band,
        confidence=result.confidence,
        temp_mean=temp_mean,
        temp_var=temp_var,
        temp_delta=temp_mean - prev.temp_mean if prev else 0.0,
        driver=_DRIVER_LABELS.get(dominant, dominant),
        posterior=dict(result.posterior),
        report_id=result.report.report_id if result.report else None,
    )


def _render(con: Console, f: LiveFrame) -> None:
    """Draw one clean tactical block for a tick (clears the screen if interactive)."""
    if con.color:
        con.line("\033[2J\033[3J\033[H")  # clear screen + scrollback, home cursor
    band_color = _BAND_COLOR[f.band]
    trend = (
        "▲ Increasing" if f.prev_risk is not None and f.risk > f.prev_risk + 0.05
        else "▼ Decreasing" if f.prev_risk is not None and f.risk < f.prev_risk - 0.05
        else "■ Stable"
    )
    trend_color = "red" if trend.startswith("▲") else "green" if trend.startswith("▼") else "dim"
    prev = f"{f.prev_risk:.0f}%" if f.prev_risk is not None else "—"

    con.line(con.c(f"[LIVE VECTIS V3 STREAM] — Cell: {f.cell}", "cyan", "bold")
             + con.c(f"   tick {f.tick}", "dim"))
    con.line(con.c("─" * WIDTH, "green"))
    con.line(f"  Current Risk:  {con.c(f'{f.risk:.0f}% ({f.band.value.upper()})', band_color, 'bold')}")
    con.line(f"  Previous Risk: {con.c(prev, 'dim')}")
    con.line(f"  Trend:         {con.c(trend, trend_color, 'bold')}")
    con.line(f"  Primary Driver:{con.c(f' {f.driver} ({f.temp_delta:+.1f}°C)', 'white')}")
    con.line(f"  Confidence:    {con.c(f'{f.confidence * 100:.0f}%', 'cyan')}"
             + con.c(f"  (Kalman Variance: {f.temp_var:.2f})", "dim"))
    con.line()
    con.line(con.c("  SCENARIO POSTERIOR", "cyan", "bold"))
    for sid, prob in sorted(f.posterior.items(), key=lambda kv: -kv[1]):
        con.line(f"    {sid:<14} {con.bar(prob)} {con.c(f'{prob * 100:5.1f}%', 'white')}")
    con.line()
    if f.report_id:
        con.line(con.c(f"  ✦ Decision board convened → report {f.report_id}", "green"))
    else:
        con.line(con.c("  · risk steady — no new decision report this tick", "dim"))
    con.line(con.c("─" * WIDTH, "green"))


async def run_live(
    *,
    ticks: int | None = 20,
    tick_seconds: float = 2.0,
    n_iterations: int = 8_000,
    seed: int = 7,
    color: bool = True,
    out: TextIO | None = None,
    llm: LLMProvider | None = None,
) -> list[LiveFrame]:
    """Run the continuous pipeline, rendering one block per tick. Returns the frames.

    ``ticks=None`` runs until interrupted. Each tick: poll the mock feeds → publish to
    the broker → let the pipeline drain that burst (Kalman → Bayesian → MC → report) →
    render the new state.
    """
    _silence_logs()
    con = Console(out or sys.stdout, color)
    lp = _build(n_iterations=n_iterations, seed=seed, llm=llm)

    frames: list[LiveFrame] = []
    prev: LiveFrame | None = None
    tick = 0
    while ticks is None or tick < ticks:
        published = await lp.producer.poll_and_publish()
        # Consume exactly this tick's burst and drain the slow path before drawing.
        await lp.pipeline.start(max_events=published)
        frame = _frame(lp, tick, prev)
        if frame is not None:
            _render(con, frame)
            frames.append(frame)
            prev = frame
        tick += 1
        if (ticks is None or tick < ticks) and tick_seconds:
            await asyncio.sleep(tick_seconds)
    return frames


def main() -> None:
    """Console entry point — live tactical stream to stdout."""
    parser = argparse.ArgumentParser(description="VECTIS V3 live climate-risk stream.")
    parser.add_argument("--ticks", type=int, default=None,
                        help="number of ticks to run (default: until Ctrl+C).")
    parser.add_argument("--interval", type=float, default=2.0,
                        help="seconds between ticks (default: 2.0).")
    parser.add_argument("--iterations", type=int, default=8_000,
                        help="Monte Carlo iterations per forecast (default: 8000).")
    args = parser.parse_args()

    _force_utf8_stdout()
    try:
        asyncio.run(run_live(ticks=args.ticks, tick_seconds=args.interval,
                             n_iterations=args.iterations))
    except KeyboardInterrupt:
        print("\n  [STREAM CLOSED] VECTIS V3 live stream stopped.", file=sys.stderr)


if __name__ == "__main__":
    main()
