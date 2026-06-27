// TanStack Query hooks — the single boundary between React and the backend.
// Server state (caching, loading/error, refetch, invalidation) lives here so
// pages stay declarative and never call fetch directly.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { analysesApi, type RunAnalysisInput } from "@/services/analyses";
import { catalogApi } from "@/services/catalog";
import { datasetsApi } from "@/services/datasets";
import { qk } from "@/services/queryKeys";
import { useSelectionStore } from "@/stores/selectionStore";

export function useHealth() {
  return useQuery({
    queryKey: qk.health,
    queryFn: catalogApi.health,
    refetchInterval: 30_000,
    retry: false,
  });
}

export function useRegions() {
  return useQuery({ queryKey: qk.regions, queryFn: catalogApi.regions });
}

export function useAnalyses(limit = 20) {
  return useQuery({ queryKey: qk.analyses, queryFn: () => analysesApi.list(limit) });
}

export function useAnalysis(id: string | null | undefined) {
  return useQuery({
    queryKey: qk.analysis(id ?? ""),
    queryFn: () => analysesApi.get(id as string),
    enabled: !!id,
  });
}

export function useModelCard(region: string | null | undefined) {
  return useQuery({
    queryKey: qk.modelCard(region ?? ""),
    queryFn: () => catalogApi.modelCard(region as string),
    enabled: !!region,
    retry: false,
  });
}

export function useDatasets() {
  return useQuery({ queryKey: qk.datasets, queryFn: datasetsApi.list });
}

/** Run a new analysis; on success, cache it, refresh the list, and focus it. */
export function useRunAnalysis() {
  const queryClient = useQueryClient();
  const setAnalysis = useSelectionStore((s) => s.setAnalysis);
  return useMutation({
    mutationFn: (input: RunAnalysisInput) => analysesApi.run(input),
    onSuccess: (report) => {
      queryClient.setQueryData(qk.analysis(report.id), report);
      queryClient.invalidateQueries({ queryKey: qk.analyses });
      setAnalysis(report.id);
    },
  });
}
