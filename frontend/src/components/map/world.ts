import type { RegionInfo } from "@/types/api";

// Whole-globe framing for the V3 console. Centred on the Atlantic so the Americas
// and Europe/Africa are both in frame at the default zoom — the platform is global,
// not a single region. Shared by every global map view (live console + legacy pages).
export const WORLD: RegionInfo = {
  key: "global",
  label: "Global",
  country: "—",
  grid: { rows: 1, cols: 1, cells: 1 },
  bbox: { min_lat: -85, min_lon: -180, max_lat: 85, max_lon: 180 },
  center: { lat: 20, lon: -30 },
};

export const WORLD_ZOOM = 1.5;
