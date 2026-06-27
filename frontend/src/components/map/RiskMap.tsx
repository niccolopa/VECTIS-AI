import { useEffect, useRef } from "react";
import maplibregl, { type Map as MlMap, type StyleSpecification } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { mapRiskRamp } from "@/utils/risk";
import type { CellRisk, RegionInfo } from "@/types/api";

// Self-contained dark basemap: no tile server, no API key — the console renders
// fully offline. Geographic context comes from the risk cells themselves.
const DARK_STYLE: StyleSpecification = {
  version: 8,
  sources: {},
  layers: [{ id: "bg", type: "background", paint: { "background-color": "#0a0e14" } }],
};

interface Props {
  region: RegionInfo;
  cells: CellRisk[];
  selectedCellId?: string | null;
  onSelectCell?: (cellId: string) => void;
}

function toGeoJSON(cells: CellRisk[]) {
  return {
    type: "FeatureCollection" as const,
    features: cells.map((c) => ({
      type: "Feature" as const,
      id: c.cell_id,
      geometry: { type: "Point" as const, coordinates: [c.lon, c.lat] },
      properties: { risk: c.risk_score, id: c.cell_id },
    })),
  };
}

export function RiskMap({ region, cells, selectedCellId, onSelectCell }: Props) {
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<MlMap | null>(null);
  const onSelect = useRef(onSelectCell);
  onSelect.current = onSelectCell;

  // Initialize the map once for the region.
  useEffect(() => {
    if (!container.current || map.current) return;
    const m = new maplibregl.Map({
      container: container.current,
      style: DARK_STYLE,
      center: [region.center.lon, region.center.lat],
      zoom: 7.4,
      attributionControl: false,
    });
    m.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    map.current = m;
    return () => {
      m.remove();
      map.current = null;
    };
  }, [region.center.lat, region.center.lon]);

  // Render / update the risk layer when cells change.
  useEffect(() => {
    const m = map.current;
    if (!m) return;

    const apply = () => {
      const data = toGeoJSON(cells);
      const src = m.getSource("cells") as maplibregl.GeoJSONSource | undefined;
      if (src) {
        src.setData(data);
        return;
      }
      m.addSource("cells", { type: "geojson", data });
      m.addLayer({
        id: "cells-glow",
        type: "circle",
        source: "cells",
        paint: {
          "circle-radius": 18,
          "circle-blur": 1,
          "circle-opacity": 0.35,
          "circle-color": mapRiskRamp() as maplibregl.ExpressionSpecification,
        },
      });
      m.addLayer({
        id: "cells-core",
        type: "circle",
        source: "cells",
        paint: {
          "circle-radius": 7,
          "circle-color": mapRiskRamp() as maplibregl.ExpressionSpecification,
          "circle-stroke-width": 1,
          "circle-stroke-color": "rgba(255,255,255,0.25)",
        },
      });
      m.addLayer({
        id: "cells-selected",
        type: "circle",
        source: "cells",
        filter: ["==", ["get", "id"], selectedCellId ?? "__none__"],
        paint: {
          "circle-radius": 11,
          "circle-color": "rgba(0,0,0,0)",
          "circle-stroke-width": 2.5,
          "circle-stroke-color": "#ffffff",
        },
      });

      m.on("click", "cells-core", (e) => {
        const id = e.features?.[0]?.properties?.id;
        if (id && onSelect.current) onSelect.current(String(id));
      });
      m.on("mouseenter", "cells-core", () => {
        m.getCanvas().style.cursor = "pointer";
      });
      m.on("mouseleave", "cells-core", () => {
        m.getCanvas().style.cursor = "";
      });
    };

    if (m.isStyleLoaded()) apply();
    else m.once("load", apply);
  }, [cells, selectedCellId]);

  // Keep the selection ring in sync.
  useEffect(() => {
    const m = map.current;
    if (!m || !m.getLayer?.("cells-selected")) return;
    m.setFilter("cells-selected", ["==", ["get", "id"], selectedCellId ?? "__none__"]);
  }, [selectedCellId]);

  return <div ref={container} className="h-full w-full" />;
}
