// V2 dashboard client — the twin view, the What-If simulator, and the stream URL.
// Reuses the shared `http` fetch wrapper (no Axios; one HTTP path for the app).
import { API_BASE_URL, http } from "@/services/apiClient";
import type {
  TwinDashboardView,
  WhatIfRequest,
  WhatIfResult,
} from "@/types/v2";

export const dashboardApi = {
  listTwins: () => http<string[]>("/api/v1/dashboard/twins"),
  getTwin: (twinId: string) => http<TwinDashboardView>(`/api/v1/dashboard/twins/${twinId}`),
  whatIf: (req: WhatIfRequest) =>
    http<WhatIfResult>("/api/v1/dashboard/simulate/what-if", {
      method: "POST",
      body: JSON.stringify(req),
    }),
};

/** Absolute ws(s):// URL for the Session-9 state-change stream. Handles both a
 *  same-origin deploy (VITE_API_BASE_URL unset) and an explicit API base. */
export function streamSocketUrl(): string {
  const base = API_BASE_URL || window.location.origin;
  const url = new URL(base, window.location.origin);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  url.pathname = "/api/v1/stream/ws";
  return url.toString();
}
