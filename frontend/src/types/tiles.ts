// Tile-server types — 1:1 with the backend Pydantic schemas.
// Source of truth: vectis/api/routers/tiles.py → TileCell / TileResponse.
// Scores come from the Tier-0 screen only (illustrative, uncalibrated coefficients);
// a tile existing is not validation.

/** The screened hazards the tile server can score today (registry keys). */
export const SCREENED_HAZARDS = ["wildfire", "flood", "quake", "cyclone"] as const;
export type Hazard = (typeof SCREENED_HAZARDS)[number];

/** One rendered H3 cell: where it is and each screened hazard's 0–100 score. */
export interface TileCell {
  cell_id: string;
  lat: number;
  lon: number;
  hazards: Record<string, number>;
  /** Native res-5 cells this entry aggregates (1 at res ≥ 5). */
  source_cells: number;
}

export interface TileResponse {
  zoom: number;
  resolution: number;
  cells: TileCell[];
}

/** The browser's current map viewport — what every tile/stream request is scoped to. */
export interface Viewport {
  west: number;
  south: number;
  east: number;
  north: number;
  zoom: number;
}
