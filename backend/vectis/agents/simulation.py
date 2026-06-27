"""Simulation Agent.

Runs lightweight what-if scenarios — the forward-looking sensitivity layer. It
perturbs key climate drivers and re-scores the region with the same model, so
the report can say how risk responds to plausible changes (e.g. a hotter,
drier month). Bounded and deterministic; deeper simulation is a roadmap item.
"""

from __future__ import annotations

import pandas as pd

from vectis.agents.base import Agent, RunContext, StepResult
from vectis.core.schemas import AgentState
from vectis.data.pipeline.schema import FEATURE_NAMES

# Each scenario shifts engineered features by an additive delta, then clips.
_SCENARIOS: dict[str, dict[str, float]] = {
    "hotter_drier_month": {"temp_anomaly_c": 2.0, "drought_index": 0.1,
                           "humidity_pct": -10.0, "vegetation_stress": 0.1},
    "high_wind_event": {"wind_speed_kmh": 20.0},
    "wetter_conditions": {"drought_index": -0.15, "humidity_pct": 12.0,
                          "vegetation_stress": -0.1},
}
_CLIP = {"drought_index": (0.0, 1.0), "vegetation_stress": (0.0, 1.0),
         "humidity_pct": (0.0, 100.0), "wind_speed_kmh": (0.0, 200.0)}


class SimulationAgent(Agent):
    name = "simulation"
    responsibility = (
        "Run what-if scenarios by perturbing key drivers and re-scoring "
        "(what could happen next)."
    )

    def _execute(self, state: AgentState, ctx: RunContext) -> StepResult:
        result = ctx.artifacts.get("pipeline")
        predictor = ctx.artifacts.get("predictor")
        baseline = state.prediction
        if result is None or predictor is None or baseline is None:
            return StepResult(summary="Simulation skipped: no prediction available.")

        base_score = baseline.aggregate_risk_score
        scenarios: list[dict] = []
        for name, deltas in _SCENARIOS.items():
            perturbed = self._perturb(result.features, deltas)
            shifted = result.__class__(
                region_key=result.region_key, features=perturbed, source=result.source,
                raw_hash=result.raw_hash, feature_hash="scenario", has_label=False,
            )
            score = predictor.predict(shifted).aggregate_risk_score
            scenarios.append({
                "name": name,
                "risk_score": score,
                "delta": round(score - base_score, 1),
            })

        state.scenarios = scenarios
        worst = max(scenarios, key=lambda s: s["risk_score"])
        summary = (
            f"Simulated {len(scenarios)} scenarios. Worst case "
            f"'{worst['name']}' → {worst['risk_score']}/100 "
            f"({worst['delta']:+.1f} vs baseline {base_score})."
        )
        return StepResult(summary=summary, payload={"scenarios": scenarios})

    @staticmethod
    def _perturb(features: pd.DataFrame, deltas: dict[str, float]) -> pd.DataFrame:
        out = features.copy()
        for col, delta in deltas.items():
            if col in FEATURE_NAMES:
                out[col] = out[col] + delta
                if col in _CLIP:
                    lo, hi = _CLIP[col]
                    out[col] = out[col].clip(lo, hi)
        return out
