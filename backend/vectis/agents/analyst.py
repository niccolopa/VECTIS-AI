"""Data Analyst Agent.

Runs the data pipeline and computes descriptive signals — the "what is
happening" layer. It surfaces notable conditions (e.g. widespread drought, high
temperature anomalies) as plain-language signals backed by concrete statistics.
"""

from __future__ import annotations

import pandas as pd

from vectis.agents.base import Agent, RunContext, StepResult
from vectis.core.schemas import AgentState
from vectis.data.pipeline.runner import run_pipeline
from vectis.data.pipeline.schema import FEATURE_NAMES

# Thresholds above which a feature is considered "elevated" for signal reporting.
_ELEVATED = {
    "temp_anomaly_c": 4.0,
    "vegetation_stress": 0.45,
    "drought_index": 0.55,
    "wind_speed_kmh": 20.0,
}


class AnalystAgent(Agent):
    name = "data_analyst"
    responsibility = (
        "Analyze the data, detect notable conditions, and summarize explainable "
        "signals (what is happening)."
    )

    def _execute(self, state: AgentState, ctx: RunContext) -> StepResult:
        raw = ctx.artifacts["raw"]
        result = run_pipeline(raw, require_label=True)
        ctx.artifacts["pipeline"] = result

        df = result.features
        stats = self._descriptive_stats(df)
        state.data_summary["dataset_version"] = result.dataset_version
        state.data_summary["feature_stats"] = stats

        signals = self._signals(df)
        state.signals = signals

        summary = (
            f"Analyzed {len(df)} cells. "
            + (signals[0] if signals else "No notable elevated conditions detected.")
        )
        return StepResult(summary=summary, payload={"n_signals": len(signals)})

    @staticmethod
    def _descriptive_stats(df: pd.DataFrame) -> dict[str, dict[str, float]]:
        return {
            f: {
                "mean": round(float(df[f].mean()), 3),
                "p90": round(float(df[f].quantile(0.9)), 3),
                "max": round(float(df[f].max()), 3),
            }
            for f in FEATURE_NAMES
        }

    @staticmethod
    def _signals(df: pd.DataFrame) -> list[str]:
        """Human-readable signals with the share of cells crossing thresholds."""
        signals: list[str] = []
        for feature, threshold in _ELEVATED.items():
            share = float((df[feature] > threshold).mean())
            if share >= 0.25:
                pct = round(share * 100)
                signals.append(
                    f"{pct}% of cells show elevated {feature.replace('_', ' ')} "
                    f"(> {threshold})."
                )
        hist = float((df["historical_fire_count"] > 0).mean())
        if hist >= 0.2:
            signals.append(f"{round(hist * 100)}% of cells have prior recorded fires.")
        return signals
