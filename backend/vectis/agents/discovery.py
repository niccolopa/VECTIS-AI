"""Data Discovery Agent.

Identifies and acquires the raw data needed for the analysis: which connector/
sources are available for the region, the time window, and basic coverage. It
seeds the run by fetching the :class:`RawFrame` onto the context blackboard.
"""

from __future__ import annotations

from vectis.agents.base import Agent, RunContext, StepResult
from vectis.core.schemas import AgentState
from vectis.data.pipeline.schema import RAW_COLUMNS


class DiscoveryAgent(Agent):
    name = "data_discovery"
    responsibility = (
        "Identify and acquire the data sources required for the question; "
        "record coverage and limitations."
    )

    def _execute(self, state: AgentState, ctx: RunContext) -> StepResult:
        raw = ctx.connector.fetch(ctx.region, window_days=state.request.window_days)
        ctx.artifacts["raw"] = raw

        state.region_label = ctx.region.label
        state.data_summary.update(
            {
                "source": raw.source,
                "raw_hash": raw.content_hash,
                "n_cells": int(len(raw.frame)),
                "window_days": state.request.window_days,
                "columns_available": [c for c in RAW_COLUMNS if c in raw.frame.columns],
            }
        )
        summary = (
            f"Acquired {len(raw.frame)} cells for {ctx.region.label} from "
            f"'{raw.source}' (window {state.request.window_days}d)."
        )
        return StepResult(summary=summary, payload={"raw_hash": raw.content_hash})
