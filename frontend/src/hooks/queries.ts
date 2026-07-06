// TanStack Query hooks — the single boundary between React and the backend.
// Server state (caching, loading/error, refetch, invalidation) lives here so
// pages stay declarative and never call fetch directly.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

import { analysesApi, type RunAnalysisInput } from "@/services/analyses";
import { catalogApi } from "@/services/catalog";
import { datasetsApi } from "@/services/datasets";
import { qk } from "@/services/queryKeys";
import { DEFAULT_REGION, useSelectionStore } from "@/stores/selectionStore";

export function useHealth() {
  return useQuery({
    queryKey: qk.health,
    queryFn: catalogApi.health,
    refetchInterval: 30_000,
    retry: false,
  });
}

export function useRegions() {
  const query = useQuery({ queryKey: qk.regions, queryFn: catalogApi.regions });
  const regionKey = useSelectionStore((s) => s.regionKey);
  const setRegion = useSelectionStore((s) => s.setRegion);

  // Failsafe: if the persisted region (e.g. stale localStorage from an older
  // build) is not in the backend list, fall back to the default — or the first
  // available — so we never render/fetch a region the backend doesn't know.
  useEffect(() => {
    const regions = query.data;
    if (!regions || regions.length === 0) return;
    if (regions.some((r) => r.key === regionKey)) return;
    const fallback = regions.find((r) => r.key === DEFAULT_REGION) ?? regions[0];
    setRegion(fallback.key);
  }, [query.data, regionKey, setRegion]);

  return query;
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

/** Delete a stored report; on success, drop its cache and refresh the list. */
export function useDeleteAnalysis() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => analysesApi.remove(id),
    onSuccess: (_void, id) => {
      queryClient.removeQueries({ queryKey: qk.analysis(id) });
      queryClient.invalidateQueries({ queryKey: qk.analyses });
    },
  });
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
