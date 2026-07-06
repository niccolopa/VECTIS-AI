// Centralized TanStack Query keys — one place to keep cache keys consistent and
// avoid typos across hooks.
export const qk = {
  health: ["health"] as const,
  regions: ["regions"] as const,
  analyses: ["analyses"] as const,
  analysis: (id: string) => ["analyses", id] as const,
  modelCard: (region: string) => ["models", region] as const,
  datasets: ["datasets"] as const,
  tiles: (v: { west: number; south: number; east: number; north: number; zoom: number }) =>
    // Round the bbox so sub-meter pan jitter doesn't mint new cache entries.
    ["tiles", v.west.toFixed(3), v.south.toFixed(3), v.east.toFixed(3), v.north.toFixed(3), Math.round(v.zoom)] as const,
  cellBrief: (cellId: string) => ["cells", cellId, "brief"] as const,
  connectorStatus: ["connectors", "status"] as const,
};
