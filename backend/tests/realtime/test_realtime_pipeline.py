"""Session 22 — the Real-Time Forecasting Pipeline end to end.

Asserts a single injected event traverses the whole flow:
Broker -> Kalman update -> Bayesian update -> Monte Carlo -> Decision Report.
All LLM calls go through a spy provider, so the board runs offline at zero API cost.
"""

from __future__ import annotations

import asyncio
from typing import Any

from vectis.agents.board.service import SimulationBoardService
from vectis.agents.llm.base import LLMProvider, NarrationResult
from vectis.realtime import ContinuousPipeline, build_default_pipeline
from vectis.realtime.connectors.weather import WeatherEvent
from vectis.realtime.events.base import GeoPoint
from vectis.realtime.streams.broker import DEFAULT_TOPIC, MemoryBroker

CELL = "44.4,8.9"
LOC = GeoPoint(lat=44.4, lon=8.9)


class _SpyLLM(LLMProvider):
    """Records every narration so we can prove the board actually ran (no API call)."""

    name = "spy"

    def __init__(self) -> None:
        self.calls = 0

    def narrate(self, *, instruction: str, context: dict[str, Any], fallback: str,
                max_tokens: int = 600) -> NarrationResult:
        self.calls += 1
        return NarrationResult(text=fallback, used_llm=False)


def _drought_event(value: float = 0.85) -> WeatherEvent:
    """An Extreme Drought reading for the California cell (a confident measurement, std=0.05)."""
    return WeatherEvent(source="test_feed", location=LOC,
                        payload={"variable": "drought_index", "value": value, "std": 0.05})


def _pipeline(spy: _SpyLLM, **kw: Any) -> ContinuousPipeline:
    return build_default_pipeline(
        broker=MemoryBroker(), board=SimulationBoardService(llm=spy),
        n_iterations=2000, **kw,
    )


def test_event_traverses_full_pipeline() -> None:
    """Broker -> Kalman -> Bayesian -> Monte Carlo -> Report, from one extreme-drought event."""
    spy = _SpyLLM()
    pipe = _pipeline(spy)

    async def scenario() -> int:
        await pipe._broker.publish(DEFAULT_TOPIC, _drought_event())
        return await pipe.start(max_events=1)

    processed = asyncio.run(scenario())

    assert processed == 1
    assert pipe.forecasts_run == 1  # Monte Carlo ran
    result = pipe.results[CELL]
    # Bayesian shifted belief away from baseline toward the drought-driven branch.
    assert result.posterior["hotter_drier"] > result.posterior["baseline"]
    # Monte Carlo produced a per-scenario outcome for every branch.
    assert {o.scenario_id for o in result.run.outcomes} == {"baseline", "hotter_drier", "extreme_wind"}
    # The first observation always crosses the threshold -> a decision report was generated.
    assert result.report is not None
    assert pipe.reports_generated == 1
    assert spy.calls > 0  # the LLM board genuinely ran (mocked)


def test_burst_for_one_cell_coalesces_to_latest_forecast() -> None:
    """A burst of events collapses to one forecast of the freshest state — throughput guard."""
    spy = _SpyLLM()
    pipe = _pipeline(spy)

    async def scenario() -> int:
        for value in (0.4, 0.6, 0.9):  # three readings, same cell, before the worker drains
            await pipe._broker.publish(DEFAULT_TOPIC, _drought_event(value))
        return await pipe.start(max_events=3)

    processed = asyncio.run(scenario())

    assert processed == 3  # every event consumed + acked
    assert pipe.forecasts_run == 1  # but only one Monte Carlo cycle (coalesced)


def test_unchanged_risk_skips_the_expensive_board() -> None:
    """The board only re-runs on a material risk move (damps LLM churn)."""
    spy = _SpyLLM()
    pipe = _pipeline(spy)
    pipe._risk_change_threshold = 1000.0  # nothing ever counts as a material move
    pipe._last_risk[CELL] = 0.0  # pretend we already reported (so it's not the first forecast)

    async def scenario() -> None:
        await pipe._broker.publish(DEFAULT_TOPIC, _drought_event())
        await pipe.start(max_events=1)

    asyncio.run(scenario())

    assert pipe.forecasts_run == 1  # the forecast still computes
    assert pipe.reports_generated == 0  # but the board is skipped
    assert pipe.results[CELL].report is None
