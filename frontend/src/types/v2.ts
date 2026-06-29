// V2 (Simulation & Forecasting) types — 1:1 with the backend Pydantic schemas.
// Source of truth on the server side:
//   - vectis/simulation/schemas.py        → ProbabilityDistribution
//   - vectis/digital_twin/schemas.py       → RiskState
//   - vectis/digital_twin/entities/region  → RegionState
//   - vectis/agents/board/schemas.py       → DecisionIntelligenceReport (+ parts)
//   - vectis/services/dashboard_service.py → ScenarioProjection / TwinDashboardView / WhatIf*
//   - vectis/streaming/events.py           → StateChange (WebSocket push)
// Keep these in lockstep with the backend — this is the type contract the whole
// dashboard (Recharts/D3 charts included) is built on.

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

/** The physical, user-editable state of a region twin (the What-If sliders map here). */
export interface RegionState {
  temperature_anomaly: number; // °C above baseline
  humidity_level: number; // %
  vegetation_stress: number; // 0–100 dryness index
  recent_fire_history: number; // count of recent detections
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

// ── Dashboard composite payloads ──────────────────────────────────────────────
export interface TwinDashboardView {
  twin_id: string;
  kind: string;
  state: RegionState;
  risk: RiskState;
  scenarios: ScenarioProjection[];
  report: DecisionIntelligenceReport;
}

/** What-If deltas — any omitted field keeps the twin's current value. */
export interface StateOverrides {
  temperature_anomaly?: number;
  humidity_level?: number;
  vegetation_stress?: number;
  recent_fire_history?: number;
}

export interface WhatIfRequest {
  twin_id: string;
  overrides: StateOverrides;
  n_iterations?: number;
}

export interface WhatIfResult {
  twin_id: string;
  state: RegionState;
  risk: RiskState;
  scenarios: ScenarioProjection[];
}

// ── Real-time stream (Session 9 WebSocket) ───────────────────────────────────
export interface StateChange {
  type: "state_changed";
  event_id: string;
  triggered_rerun: boolean;
  belief_shift: number;
  risk: RiskState;
}

/** A point on the Probability Timeline, accumulated client-side from the stream. */
export interface TimelinePoint {
  t: string; // ISO timestamp
  risk: number; // 0–100
  confidence: number; // 0–1
  band: RiskBand;
}
