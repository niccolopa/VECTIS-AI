// Belief-history API — the durable trajectory store behind /terminal's playback.
// Reads the Session-39 snapshots (api/routers/history.py); everything here is a
// past recording, never a live number.
import { http } from "@/services/apiClient";
import type { CellHistory, PlaybackResponse } from "@/types/history";
import type { Viewport } from "@/types/tiles";

/** One cell's risk × confidence × belief trajectory over a time range. */
export function fetchCellHistory(
  cellId: string,
  opts?: { start?: string; end?: string; limit?: number },
): Promise<CellHistory> {
  const q = new URLSearchParams();
  if (opts?.start) q.set("start", opts.start);
  if (opts?.end) q.set("end", opts.end);
  if (opts?.limit != null) q.set("limit", String(opts.limit));
  const qs = q.toString();
  return http<CellHistory>(`/api/v1/history/cells/${cellId}${qs ? `?${qs}` : ""}`);
}

/** Time-sliced viewport frames for the map's scrubbable history. */
export function fetchPlaybackFrames(
  viewport: Viewport,
  opts: { start?: string; end?: string; steps?: number } = {},
): Promise<PlaybackResponse> {
  const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, v));
  const q = new URLSearchParams({
    west: clamp(viewport.west, -180, 180).toFixed(3),
    south: clamp(viewport.south, -90, 90).toFixed(3),
    east: clamp(viewport.east, -180, 180).toFixed(3),
    north: clamp(viewport.north, -90, 90).toFixed(3),
  });
  if (opts.start) q.set("start", opts.start);
  if (opts.end) q.set("end", opts.end);
  if (opts.steps != null) q.set("steps", String(opts.steps));
  return http<PlaybackResponse>(`/api/v1/history/frames?${q.toString()}`);
}
