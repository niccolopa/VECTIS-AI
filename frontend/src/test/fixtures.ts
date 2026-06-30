// Shared test fixtures shaped exactly like the backend responses.
import type {
  AnalysisSummary,
  DecisionReport,
  HealthStatus,
  RegionInfo,
} from "@/types/api";

export const healthFixture: HealthStatus = {
  status: "ok",
  version: "1.0.0",
  env: "test",
  llm_provider: "mock",
};

export const regionFixture: RegionInfo = {
  key: "liguria",
  label: "Global View",
  country: "IT",
  grid: { rows: 12, cols: 20, cells: 240 },
  bbox: { min_lat: 43.78, min_lon: 7.49, max_lat: 44.68, max_lon: 10.07 },
  center: { lat: 44.23, lon: 8.78 },
};

export const reportFixture: DecisionReport = {
  id: "abc123def456",
  region: "liguria",
  area_label: "Global View",
  generated_at: "2026-06-27T10:00:00+00:00",
  risk_score: 76.7,
  risk_band: "severe",
  confidence: 0.89,
  summary: "Global monitoring shows severe wildfire risk driven by drought and vegetation stress.",
  drivers: [
    { name: "Drought conditions", feature: "drought_index", value: 0.6, contribution: 0.37, direction: "increases", description: "" },
    { name: "Vegetation stress", feature: "vegetation_stress", value: 0.5, contribution: 0.21, direction: "increases", description: "" },
  ],
  evidence: [
    { source: "model:shap", statement: "Drought conditions increases risk", metric: "drought_index", value: 0.37 },
    { source: "model_card", statement: "Model discrimination ROC-AUC=0.907.", metric: "roc_auc", value: 0.907 },
  ],
  recommended_actions: [
    { action: "Increase monitoring of high-risk cells", rationale: "Aggregate risk is high.", priority: "high" },
  ],
  cell_risks: [
    { cell_id: "liguria-000", lat: 44.0, lon: 8.0, risk_score: 80 },
    { cell_id: "liguria-001", lat: 44.1, lon: 8.2, risk_score: 40 },
  ],
  critic_review: { approved: true, revision_count: 0, issues: [], notes: "Report substantiated." },
  model_card_ref: "liguria/logistic_regression@v1",
  trace: [
    { agent: "ml_research", summary: "Scored region risk 76.7/100.", duration_ms: 12, used_llm: false, payload: {} },
    {
      agent: "simulation",
      summary: "Simulated scenarios.",
      duration_ms: 8,
      used_llm: false,
      payload: {
        scenarios: [
          { name: "hotter_drier_month", risk_score: 88.9, delta: 12.2 },
          { name: "wetter_conditions", risk_score: 61.0, delta: -15.7 },
        ],
      },
    },
  ],
};

export const summaryFixture: AnalysisSummary = {
  id: reportFixture.id,
  region: "liguria",
  area_label: "Global View",
  risk_score: 76.7,
  risk_band: "severe",
  confidence: 0.89,
  approved: true,
  generated_at: reportFixture.generated_at,
};
