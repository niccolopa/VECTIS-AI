// V2 dashboard hooks — the React↔backend boundary for the twin view + What-If.
// Same pattern as hooks/queries.ts: server state lives here, components stay declarative.
import { useMutation, useQuery } from "@tanstack/react-query";

import { dashboardApi } from "@/services/dashboard";
import { qk } from "@/services/queryKeys";
import type { WhatIfRequest } from "@/types/v2";

export function useTwins() {
  return useQuery({ queryKey: qk.twins, queryFn: dashboardApi.listTwins });
}

export function useTwinView(twinId: string | null | undefined) {
  return useQuery({
    queryKey: qk.twin(twinId ?? ""),
    queryFn: () => dashboardApi.getTwin(twinId as string),
    enabled: !!twinId,
  });
}

/** Run a manual What-If; results are deterministic + backend-cached, so no extra
 *  client caching is needed — the mutation just returns the recomputed posture. */
export function useWhatIf() {
  return useMutation({
    mutationFn: (req: WhatIfRequest) => dashboardApi.whatIf(req),
  });
}
