// V2 (Simulation & Forecasting) types — 1:1 with the backend Pydantic schemas.
// Source of truth on the server side:
//   - vectis/simulation/schemas.py        → ProbabilityDistribution
//   - vectis/digital_twin/schemas.py       → RiskState
//   - vectis/agents/board/schemas.py       → DecisionIntelligenceReport (+ parts)
// Keep these in lockstep with the backend — this is the type contract the shared
// scenario/brief components (Recharts/D3 charts included) are built on.

import type { RiskBand } from "@/types/api";

export type { RiskBand };

/** A reduced Monte Carlo outcome — everything a box-and-whisker / fan chart needs. */
export interface ProbabilityDistribution {
  variable: string;
  mean: number;
  std: number;
  p05: number;
  p50: number;
  p95: number;
  /** Tail probabilities keyed by threshold name, e.g. { high: 0.8, severe: 0.5 }. */
  exceedance: Record<string, number>;
  /** Raw samples — only present when the run retained them (usually null). */
  samples?: number[] | null;
}

/** A twin's posterior-weighted risk picture (the aggregate "headline" number). */
export interface RiskState {
  region: string;
  risk: number; // 0–100
  band: RiskBand;
  confidence: number; // 0–1
  scenario_priors: Record<string, number>;
  updated_at: string; // ISO datetime
}

/** One scenario branch + its full outcome distribution (the Scenario Explorer unit). */
export interface ScenarioProjection {
  id: string;
  name: string;
  description: string;
  probability: number; // posterior weight, 0–1
  expected_band: RiskBand;
  risk: ProbabilityDistribution;
}

// ── AI Decision Intelligence Report (LangGraph board output) ──────────────────
export interface ScenarioView {
  id: string;
  name: string;
  description: string;
  probability: number;
}

export interface BoardInput {
  region: string;
  risk_score: number;
  confidence: number;
  risk_band: RiskBand;
  primary_driver: string;
  scenarios: ScenarioView[];
}

export interface AnalystBrief {
  summary: string;
  risk_score: number;
  confidence_pct: number;
  risk_band: RiskBand;
  primary_driver: string;
}

export interface ScenarioNarrative {
  scenario_id: string;
  name: string;
  probability_pct: number;
  storyline: string;
}

export interface DebateRound {
  optimist_case: string;
  pessimist_case: string;
}

export interface RedTeamCritique {
  challenge: string;
  blind_spots: string[];
  residual_uncertainty_pct: number;
}

export interface DecisionIntelligenceReport {
  report_id: string;
  classification: string;
  region: string;
  generated_at: string;
  bottom_line: string;
  source: BoardInput;
  analyst: AnalystBrief;
  scenarios: ScenarioNarrative[];
  debate: DebateRound;
  red_team: RedTeamCritique;
}
