// Per-cell drill-down brief — 1:1 with the backend Pydantic schemas.
// Source of truth: vectis/api/routers/cells.py → CellBrief / CellAnalysis / ScenarioBrief.
//
// `tier` is the panel's honesty switch: "T0" means the cell has ONLY the cheap
// screening estimate (measured biased low by up to ~13 pts in the mid-risk band,
// Session 32) and must never be presented with the visual weight of a full
// Monte Carlo distribution.

import type { RiskBand } from "@/types/api";
import type { DecisionIntelligenceReport, ProbabilityDistribution } from "@/types/v2";

export type CellTier = "T0" | "T1" | "T2";

export interface ScenarioBrief {
  id: string;
  probability: number; // posterior weight, 0–1
  expected_band: RiskBand;
  risk: ProbabilityDistribution;
}

export interface CellAnalysis {
  risk: number;
  band: RiskBand;
  confidence: number;
  posterior: Record<string, number>;
  scenarios: ScenarioBrief[];
  report: DecisionIntelligenceReport | null;
}

export interface CellStateView {
  cell_id: string;
  temperature: number | null;
  humidity: number | null;
  drought_index: number | null;
  fire_risk: number | null;
  precipitation_mm: number | null;
  earthquake_magnitude: number | null;
  flood_alert_level: number | null;
  cyclone_alert_level: number | null;
  extra: Record<string, number>;
  version: number;
  last_updated: string; // ISO
  sources: string[];
}

export interface CellBrief {
  cell_id: string;
  lat: number;
  lon: number;
  tier: CellTier;
  state: CellStateView | null;
  screening: Record<string, number>; // hazard → 0–100 point estimate
  /** Native res-5 cells this brief aggregates (>1 when a coarse map cell was clicked). */
  source_cells: number;
  analysis: CellAnalysis | null;
}
