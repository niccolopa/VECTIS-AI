// V3 live stream — the SSE endpoint URL. SSE rides plain HTTP, so it reuses the same
// API base as every other call (no ws:// scheme juggling like the V2 socket).
import { API_BASE_URL, http } from "@/services/apiClient";

/** Stable per-browser viewer id (Session 38): the backend attention registry keys
 * viewports and watchlist pins on it, so a pan's SSE reconnect and the watchlist
 * sync all speak for the same viewer. Persisted; falls back to a per-session id
 * when storage is unavailable. */
export function viewerId(): string {
  const KEY = "vectis-viewer-id";
  try {
    let id = window.localStorage.getItem(KEY);
    if (!id) {
      id = `v-${Math.random().toString(36).slice(2, 14)}`;
      window.localStorage.setItem(KEY, id);
    }
    return id;
  } catch {
    return "v-session";
  }
}

/** Best-effort push of the full pinned set to the backend (idempotent PUT).
 * Pins are client-persisted; this sync is what buys them compute priority and
 * eviction protection server-side — failure degrades to Session-37 bookmark
 * behavior, never breaks the UI. */
export function syncWatchlist(cells: string[]): Promise<void> {
  return http<void>(`/api/v1/watchlist/${viewerId()}`, {
    method: "PUT",
    body: JSON.stringify({ cells }),
  }).catch(() => undefined);
}

/** Absolute URL for the V3 continuous-intelligence SSE stream. */
export function liveStreamUrl(interval?: number): string {
  const base = API_BASE_URL || window.location.origin;
  const url = new URL("/api/v1/stream/v3/live", base);
  if (interval != null) url.searchParams.set("interval", String(interval));
  return url.toString();
}

/** Absolute URL for the viewport-scoped terminal SSE stream (Session 37).
 *
 * The bbox is rounded so sub-meter pan jitter doesn't force an SSE reconnect,
 * and clamped to valid lat/lon (a world-wrapped map can report lon beyond ±180).
 */
export function terminalStreamUrl(viewport: {
  west: number;
  south: number;
  east: number;
  north: number;
  zoom: number;
}): string {
  const base = API_BASE_URL || window.location.origin;
  const url = new URL("/api/v1/stream/v3/terminal", base);
  const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, v));
  url.searchParams.set("west", clamp(viewport.west, -180, 180).toFixed(3));
  url.searchParams.set("south", clamp(viewport.south, -90, 90).toFixed(3));
  url.searchParams.set("east", clamp(viewport.east, -180, 180).toFixed(3));
  url.searchParams.set("north", clamp(viewport.north, -90, 90).toFixed(3));
  url.searchParams.set("zoom", String(Math.round(clamp(viewport.zoom, 0, 22))));
  url.searchParams.set("viewer", viewerId());
  return url.toString();
}
