// Real backend clients for reference data: regions, model cards, health.
import { http } from "@/services/apiClient";
import type { HealthStatus, ModelCard, RegionInfo } from "@/types/api";

export const catalogApi = {
  regions: () => http<RegionInfo[]>("/api/v1/regions"),
  modelCard: (region: string) => http<ModelCard>(`/api/v1/models/${region}`),
  health: () => http<HealthStatus>("/health"),
};
