// useTiles — viewport-scoped tile fetching. One query per (rounded bbox, zoom);
// the WorldRiskMap's debounced onViewportChange drives the key, so the endpoint is
// only ever asked for what is on screen. Previous data is kept while a pan's fresh
// tiles load, so the choropleth never blinks empty mid-gesture.
import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { qk } from "@/services/queryKeys";
import { fetchTiles } from "@/services/tiles";
import type { TileCell, Viewport } from "@/types/tiles";

// The Tier-0 screen refreshes as global feeds land (~30 s cadence); refetch on the
// same clock so a parked viewport stays current without hammering the cache.
const TILE_REFRESH_MS = 30_000;

export function useTiles(viewport: Viewport | null): {
  cells: TileCell[];
  resolution: number | null;
  isLoading: boolean;
} {
  const query = useQuery({
    queryKey: viewport ? qk.tiles(viewport) : ["tiles", "idle"],
    queryFn: () => fetchTiles(viewport!),
    enabled: viewport != null,
    placeholderData: keepPreviousData,
    refetchInterval: TILE_REFRESH_MS,
  });
  return {
    cells: query.data?.cells ?? [],
    resolution: query.data?.resolution ?? null,
    isLoading: query.isLoading,
  };
}
