// WorldRiskMap — the tiled globe. Renders the Session-36 tile endpoint's H3 cells as
// a MapLibre choropleth (real hex footprints via h3-js, not dots) on the same dark
// tactical basemap as RiskMap, and reports every debounced pan/zoom as a viewport so
// the page re-fetches tiles scoped to exactly what is on screen — never more.
//
// Hazard compositing happens here, client-side: the tile response carries every
// screened hazard per cell, and each cell is painted by the MAX score over the
// currently-enabled hazards (the same "a hot hazard must never be averaged away"
// rule the backend's roll-up uses). Toggling a hazard is therefore instant — no
// refetch, one setData.
import { useEffect, useRef } from "react";
import maplibregl, { type Map as MlMap } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { cellToBoundary } from "h3-js";

import { DARK_STYLE } from "@/components/map/RiskMap";
import { WORLD, WORLD_ZOOM } from "@/components/map/world";
import { mapRiskRamp } from "@/utils/risk";
import type { TileCell, Viewport } from "@/types/tiles";

const VIEWPORT_DEBOUNCE_MS = 250;

/** Max score over the enabled hazards — the composite the cell is painted with. */
export function compositeRisk(cell: TileCell, active: string[]): number | null {
  let max: number | null = null;
  for (const hazard of active) {
    const score = cell.hazards[hazard];
    if (score != null && (max == null || score > max)) max = score;
  }
  return max;
}

function toGeoJSON(cells: TileCell[], activeHazards: string[]) {
  const features = [];
  for (const c of cells) {
    const risk = compositeRisk(c, activeHazards);
    if (risk == null) continue; // no enabled hazard has a score → nothing honest to paint
    // ponytail: cells straddling the antimeridian render smeared (h3-js boundary
    // longitudes jump ±360); acceptable until operators work the Pacific seam.
    const ring = cellToBoundary(c.cell_id, true); // [lng, lat] pairs, closed loop
    features.push({
      type: "Feature" as const,
      id: c.cell_id,
      geometry: { type: "Polygon" as const, coordinates: [ring] },
      properties: { risk, id: c.cell_id, lat: c.lat, lon: c.lon },
    });
  }
  return { type: "FeatureCollection" as const, features };
}

function readViewport(m: MlMap): Viewport {
  const b = m.getBounds();
  return {
    west: b.getWest(),
    south: b.getSouth(),
    east: b.getEast(),
    north: b.getNorth(),
    zoom: m.getZoom(),
  };
}

interface Props {
  cells: TileCell[];
  /** Hazards currently toggled on; cells are painted by their max enabled score. */
  activeHazards: string[];
  selectedCellId?: string | null;
  onSelectCell?: (cell: { cellId: string; lat: number; lon: number }) => void;
  /** Fired (debounced) after every pan/zoom with the new visible bbox + zoom. */
  onViewportChange?: (viewport: Viewport) => void;
  /** Imperative recenter target (watchlist click); the map flies there when it changes. */
  focus?: { lat: number; lon: number } | null;
}

export function WorldRiskMap({
  cells,
  activeHazards,
  selectedCellId,
  onSelectCell,
  onViewportChange,
  focus,
}: Props) {
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<MlMap | null>(null);
  const onSelect = useRef(onSelectCell);
  onSelect.current = onSelectCell;
  const onViewport = useRef(onViewportChange);
  onViewport.current = onViewportChange;

  // Initialize once, framed on the whole globe.
  useEffect(() => {
    if (!container.current || map.current) return;
    const m = new maplibregl.Map({
      container: container.current,
      style: DARK_STYLE,
      center: [WORLD.center.lon, WORLD.center.lat],
      zoom: WORLD_ZOOM,
      attributionControl: false,
    });
    m.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    map.current = m;

    // Debounced viewport reporting: `moveend` fires once per gesture, the timer
    // coalesces gesture bursts (wheel-zoom steps) into one tile refetch.
    let timer: ReturnType<typeof setTimeout> | undefined;
    const report = () => {
      clearTimeout(timer);
      timer = setTimeout(() => onViewport.current?.(readViewport(m)), VIEWPORT_DEBOUNCE_MS);
    };
    m.on("moveend", report);
    const emitInitial = () => onViewport.current?.(readViewport(m));
    if (m.isStyleLoaded()) emitInitial();
    else m.once("load", emitInitial);

    return () => {
      clearTimeout(timer);
      m.remove();
      map.current = null;
    };
  }, []);

  // Paint / repaint the choropleth when cells or the hazard toggle change.
  useEffect(() => {
    const m = map.current;
    if (!m) return;

    const apply = () => {
      const data = toGeoJSON(cells, activeHazards);
      const src = m.getSource("tiles") as maplibregl.GeoJSONSource | undefined;
      if (src) {
        src.setData(data);
        return;
      }
      m.addSource("tiles", { type: "geojson", data });
      m.addLayer({
        id: "tiles-fill",
        type: "fill",
        source: "tiles",
        paint: {
          "fill-color": mapRiskRamp() as maplibregl.ExpressionSpecification,
          "fill-opacity": 0.4,
        },
      });
      m.addLayer({
        id: "tiles-outline",
        type: "line",
        source: "tiles",
        paint: {
          "line-color": mapRiskRamp() as maplibregl.ExpressionSpecification,
          "line-width": 1,
          "line-opacity": 0.8,
        },
      });
      m.addLayer({
        id: "tiles-selected",
        type: "line",
        source: "tiles",
        filter: ["==", ["get", "id"], selectedCellId ?? "__none__"],
        paint: { "line-color": "#ffffff", "line-width": 2.5 },
      });

      m.on("click", "tiles-fill", (e) => {
        const p = e.features?.[0]?.properties;
        if (p?.id && onSelect.current) {
          onSelect.current({ cellId: String(p.id), lat: Number(p.lat), lon: Number(p.lon) });
        }
      });
      m.on("mouseenter", "tiles-fill", () => {
        m.getCanvas().style.cursor = "pointer";
      });
      m.on("mouseleave", "tiles-fill", () => {
        m.getCanvas().style.cursor = "";
      });
    };

    if (m.isStyleLoaded()) apply();
    else m.once("load", apply);
  }, [cells, activeHazards, selectedCellId]);

  // Keep the selection ring in sync.
  useEffect(() => {
    const m = map.current;
    if (!m || !m.getLayer?.("tiles-selected")) return;
    m.setFilter("tiles-selected", ["==", ["get", "id"], selectedCellId ?? "__none__"]);
  }, [selectedCellId]);

  // Fly to a requested focus point (watchlist re-center).
  useEffect(() => {
    if (focus && map.current) {
      map.current.flyTo({ center: [focus.lon, focus.lat], zoom: Math.max(map.current.getZoom(), 6) });
    }
  }, [focus]);

  return <div ref={container} className="h-full w-full" />;
}
