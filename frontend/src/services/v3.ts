// V3 live stream — the SSE endpoint URL. SSE rides plain HTTP, so it reuses the same
// API base as every other call (no ws:// scheme juggling like the V2 socket).
import { API_BASE_URL } from "@/services/apiClient";

/** Absolute URL for the V3 continuous-intelligence SSE stream. */
export function liveStreamUrl(interval?: number): string {
  const base = API_BASE_URL || window.location.origin;
  const url = new URL("/api/v1/stream/v3/live", base);
  if (interval != null) url.searchParams.set("interval", String(interval));
  return url.toString();
}
