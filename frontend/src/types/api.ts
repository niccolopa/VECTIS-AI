// Types mirroring the backend Pydantic contracts in backend/vectis/core/schemas.py.
// Keep in sync with that file — it is the single source of truth.

export type RiskBand = "low" | "moderate" | "severe" | "high";
export type Direction = "increases" | "decreases";
export type Priority = "low" | "medium" | "high";
export type Severity = "info" | "warning" | "blocker";

export interface Driver {
  name: string;
  feature: string;
  value: number;
  contribution: number;
  direction: Direction;
  description: string;
}

export interface Evidence {
  source: string;
  statement: string;
  metric: string | null;
  value: number | null;
}

export interface RecommendedAction {
  action: string;
  rationale: string;
  priority: Priority;
}

export interface CriticIssue {
  severity: Severity;
  claim: string;
  problem: string;
}

export interface CriticReview {
  approved: boolean;
  revision_count: number;
  issues: CriticIssue[];
  notes: string;
}

export interface CellRisk {
  cell_id: string;
  lat: number;
  lon: number;
  risk_score: number;
}

export interface AgentTrace {
  agent: string;
  summary: string;
  duration_ms: number;
  used_llm: boolean;
  payload: Record<string, unknown>;
}

/** A what-if scenario as produced by the Simulation agent (read from the trace). */
export interface Scenario {
  name: string;
  risk_score: number;
  delta: number;
}

export interface DecisionReport {
  id: string;
  region: string;
  area_label: string;
  generated_at: string;
  risk_score: number;
  risk_band: RiskBand;
  confidence: number;
  summary: string;
  drivers: Driver[];
  evidence: Evidence[];
  recommended_actions: RecommendedAction[];
  cell_risks: CellRisk[];
  critic_review: CriticReview;
  model_card_ref: string;
  trace: AgentTrace[];
}

/** Lightweight row returned by GET /api/v1/analyses. */
export interface AnalysisSummary {
  id: string;
  region: string;
  area_label: string;
  risk_score: number;
  risk_band: RiskBand;
  confidence: number;
  approved: boolean;
  generated_at: string;
}

export interface RegionInfo {
  key: string;
  label: string;
  country: string;
  grid: { rows: number; cols: number; cells: number };
  bbox: { min_lat: number; min_lon: number; max_lat: number; max_lon: number };
  center: { lat: number; lon: number };
}

export interface ModelCard {
  model_name: string;
  region: string;
  dataset_version: string;
  feature_names: string[];
  metrics: Record<string, number>;
  candidates: Record<string, Record<string, number>>;
  created_at: string;
  seed: number;
  notes: string;
}

export interface HealthStatus {
  status: string;
  version: string;
  env: string;
  llm_provider: string;
}
