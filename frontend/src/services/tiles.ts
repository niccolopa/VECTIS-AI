// Tile endpoint client — GET /api/v1/tiles scoped to the visible viewport only.
// The whole point of the Session-36 tile server: the map asks for exactly what is
// on screen, and the backend answers from the cheap Tier-0 screen (never T1/T2).
import { http } from "@/services/apiClient";
import type { TileResponse, Viewport } from "@/types/tiles";

const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, v));

/** Fetch screened per-hazard risk for the viewport bbox at the current zoom.
 *
 * Bounds are clamped to valid lat/lon: a world-wrapped MapLibre viewport can report
 * longitudes beyond ±180, which the backend rejects. ponytail: clamping (not
 * splitting) an antimeridian-crossing bbox matches the backend's own documented
 * limitation — split client-side if operators ever work the Pacific seam.
 */
export function fetchTiles(viewport: Viewport): Promise<TileResponse> {
  const params = new URLSearchParams({
    west: String(clamp(viewport.west, -180, 180)),
    south: String(clamp(viewport.south, -90, 90)),
    east: String(clamp(viewport.east, -180, 180)),
    north: String(clamp(viewport.north, -90, 90)),
    zoom: String(Math.round(clamp(viewport.zoom, 0, 22))),
  });
  return http<TileResponse>(`/api/v1/tiles?${params.toString()}`);
}
