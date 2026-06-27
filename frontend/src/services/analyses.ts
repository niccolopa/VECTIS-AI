// Real backend client for analyses (POST/GET /api/v1/analyses).
import { http } from "@/services/apiClient";
import type { AnalysisSummary, DecisionReport, Scenario } from "@/types/api";

export interface RunAnalysisInput {
  region: string;
}

export const analysesApi = {
  run: (input: RunAnalysisInput) =>
    http<DecisionReport>("/api/v1/analyses", {
      method: "POST",
      body: JSON.stringify(input),
    }),
  list: (limit = 20) => http<AnalysisSummary[]>(`/api/v1/analyses?limit=${limit}`),
  get: (id: string) => http<DecisionReport>(`/api/v1/analyses/${id}`),
};

/** Extract the Simulation agent's scenarios from a report's trace (real data). */
export function scenariosFromReport(report: DecisionReport): Scenario[] {
  const sim = report.trace.find((t) => t.agent === "simulation");
  const raw = sim?.payload?.scenarios;
  return Array.isArray(raw) ? (raw as Scenario[]) : [];
}
