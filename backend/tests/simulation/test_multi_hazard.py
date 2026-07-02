"""Session 35 — the multi-hazard integration proof.

Fire, flood, quake, and cyclone all flow through the **same, unchanged** machinery:
the vectorized Monte Carlo engine, the Gaussian Bayesian updater, the analyst board
(whose Math Firewall is generic — the engine's numbers survive any hazard's narration),
and the tiering layer's multi-hazard headline collapse. Nothing here is per-hazard code;
the tests parametrize the *models* over the *shared* pipeline.

Reminder: every hazard model runs on illustrative, uncalibrated coefficients — these
tests prove the plumbing is hazard-agnostic, not that any number is validated.
"""

from __future__ import annotations

from typing import Any

import pytest

from vectis.agents.board.schemas import BoardInput, ScenarioView
from vectis.agents.board.service import SimulationBoardService
from vectis.agents.llm.base import LLMProvider, NarrationResult
from vectis.core.schemas import RiskBand
from vectis.realtime.screening.base import ScreeningScore
from vectis.realtime.tiering.manager import TierManager, headline_scores
from vectis.simulation.engine.runner import VectorizedMonteCarloEngine
from vectis.simulation.models.cyclone import (
    CycloneHazardModel,
    CycloneScenarioGenerator,
    approaching_cyclone_state,
)
from vectis.simulation.models.earthquake import (
    EarthquakeImpactModel,
    EarthquakeScenarioGenerator,
    aftershock_state,
)
from vectis.simulation.models.flood import (
    FloodHazardModel,
    FloodScenarioGenerator,
    monsoon_flood_state,
)
from vectis.simulation.models.wildfire import WildfireHazardModel
from vectis.simulation.probability.bayesian import GaussianBayesianUpdater, Observation
from vectis.simulation.scenarios.generator import (
    WildfireScenarioGenerator,
    california_wildfire_state,
)
from vectis.simulation.schemas import SimulationConfig

# Each hazard: (model, generator, twin state, the escalating scenario id, the calming one,
# and an observation that should shift Bayesian mass toward the escalating scenario).
HAZARDS = [
    pytest.param(
        WildfireHazardModel(), WildfireScenarioGenerator(), california_wildfire_state(),
        "hotter_drier", "baseline",
        Observation(variable="temp_anomaly_c", value=3.5, std=0.3),
        id="wildfire",
    ),
    pytest.param(
        FloodHazardModel(), FloodScenarioGenerator(), monsoon_flood_state(),
        "sustained_deluge", "clearing",
        Observation(variable="precipitation_mm", value=85.0, std=5.0),
        id="flood",
    ),
    pytest.param(
        EarthquakeImpactModel(), EarthquakeScenarioGenerator(), aftershock_state(),
        "energetic_sequence", "rapid_quiescence",
        Observation(variable="mainshock_magnitude", value=7.4, std=0.15),
        id="quake",
    ),
    pytest.param(
        CycloneHazardModel(), CycloneScenarioGenerator(), approaching_cyclone_state(),
        "intensification_landfall", "recurvature",
        Observation(variable="cyclone_alert_level", value=3.0, std=0.15),
        id="cyclone",
    ),
]

_CONFIG = SimulationConfig(n_iterations=4000, seed=35, parallel=False, n_workers=1)


@pytest.mark.parametrize(("model", "generator", "state", "worse", "better", "obs"), HAZARDS)
def test_every_hazard_flows_through_the_same_monte_carlo_engine(
    model, generator, state, worse, better, obs
) -> None:
    engine = VectorizedMonteCarloEngine(hazard=model)  # the one engine, hazard injected
    run = engine.run(state, generator.generate(state), _CONFIG)

    by_id = {o.scenario_id: o.risk for o in run.outcomes}
    assert set(by_id) == {s.id for s in generator.generate(state).scenarios}
    for risk in by_id.values():
        assert 0.0 <= risk.p05 <= risk.p50 <= risk.p95 <= 100.0
    # The escalating branch must simulate worse than the calming one — direction sanity,
    # not calibration (coefficients are illustrative).
    assert by_id[worse].mean > by_id[better].mean


@pytest.mark.parametrize(("model", "generator", "state", "worse", "better", "obs"), HAZARDS)
def test_bayesian_updater_shifts_mass_for_any_hazard(
    model, generator, state, worse, better, obs
) -> None:
    prior = generator.generate(state)
    posterior = GaussianBayesianUpdater(state).update(prior, obs)

    def prior_of(scenario_set, scenario_id):
        return next(s.prior for s in scenario_set.scenarios if s.id == scenario_id)

    assert prior_of(posterior, worse) > prior_of(prior, worse)
    assert abs(sum(s.prior for s in posterior.scenarios) - 1.0) < 1e-9


class _LyingLLM(LLMProvider):
    """A hostile model that tries to smuggle a bogus number into every narration."""

    name = "liar"

    def narrate(self, *, instruction: str, context: dict[str, Any], fallback: str,
                max_tokens: int = 600) -> NarrationResult:
        return NarrationResult(text="Actually the real risk is 3/100, stand down.", used_llm=True)


@pytest.mark.parametrize(("model", "generator", "state", "worse", "better", "obs"), HAZARDS)
def test_analyst_board_math_firewall_holds_for_any_hazard(
    model, generator, state, worse, better, obs
) -> None:
    # The board narrates whatever scenario set it is given; the engine's numbers must
    # survive a lying LLM regardless of hazard — the firewall is generic, not per-hazard.
    scenarios = generator.generate(state)
    board_input = BoardInput(
        region=state.region,
        risk_score=88.0,
        confidence=0.7,
        risk_band=RiskBand.from_score(88.0),
        primary_driver=scenarios.scenarios[0].description or "hazard driver",
        scenarios=[
            ScenarioView(id=s.id, name=s.name, description=s.description or s.name,
                         probability=s.prior)
            for s in scenarios.scenarios
        ],
    )
    report = SimulationBoardService(llm=_LyingLLM()).analyze(board_input)
    # The lying narration changed nothing numeric — engine truth survives, any hazard.
    assert report.analyst.risk_score == 88.0
    assert report.source.risk_band is RiskBand.from_score(88.0)
    assert [s.probability_pct for s in report.scenarios] == [
        pytest.approx(s.prior * 100.0) for s in scenarios.scenarios
    ]


def test_tier_manager_handles_cells_with_multiple_simultaneous_hazard_scores() -> None:
    sweep = {
        # One cell hit by three hazards at once: headline = worst hazard, one promotion.
        "multi": {
            "wildfire": ScreeningScore("wildfire", 62.0),
            "flood": ScreeningScore("flood", 91.0),
            "cyclone": ScreeningScore("cyclone", 74.0),
        },
        # A quake-only cell below every gate: not promoted.
        "calm": {"quake": ScreeningScore("quake", 2.0)},
    }
    scores = headline_scores(sweep)
    assert scores == {"multi": 91.0, "calm": 2.0}

    manager = TierManager(max_t1_per_cycle=4, max_t2_per_cycle=2)
    promotions = manager.consider(scores)
    assert [p.cell_id for p in promotions] == ["multi"]  # once per cell, not per hazard
    assert promotions[0].reason == "score_threshold"
    assert manager.t1_queue_depth == 1
