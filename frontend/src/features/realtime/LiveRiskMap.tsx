// LiveRiskMap — the cell on the existing MapLibre layer, recoloring continuously as
// the stream pushes new risk. Reuses RiskMap (the offline dark choropleth); the cell's
// fill follows the shared risk ramp, so the dot shifts green→amber→red as risk climbs.
// A pulsing "LIVE" ring overlays it while the stream is connected.
import { Card } from "@/components/ui";
import { RiskMap } from "@/components/map/RiskMap";
import { bandColor } from "@/utils/risk";
import type { CellRisk, RegionInfo } from "@/types/api";
import type { V3Frame } from "@/types/v3";

// Liguria centroid — the region the live feeds report against (fallback when no frame).
const LIGURIA_CENTER = { lat: 44.41, lon: 8.93 };

const REGION: RegionInfo = {
  key: "liguria",
  label: "Liguria, Italy",
  country: "Italy",
  grid: { rows: 1, cols: 1, cells: 1 },
  bbox: { min_lat: 43.8, min_lon: 7.5, max_lat: 44.7, max_lon: 10.0 },
  center: LIGURIA_CENTER,
};

function cellFromFrame(frame: V3Frame | null): CellRisk[] {
  if (!frame) return [];
  const [lat, lon] = frame.cell_id.split(",").map(Number);
  return [
    {
      cell_id: frame.cell_id,
      lat: Number.isFinite(lat) ? lat : LIGURIA_CENTER.lat,
      lon: Number.isFinite(lon) ? lon : LIGURIA_CENTER.lon,
      risk_score: frame.risk,
    },
  ];
}

export function LiveRiskMap({ frame, connected }: { frame: V3Frame | null; connected: boolean }) {
  const cells = cellFromFrame(frame);
  return (
    <Card flush className="relative h-72">
      <RiskMap region={REGION} cells={cells} />
      <div className="pointer-events-none absolute left-3 top-3 z-10 flex items-center gap-2 rounded-full border border-border-strong bg-bg/70 px-2 py-1 backdrop-blur">
        <span
          className={connected ? "h-2 w-2 rounded-full animate-pulse" : "h-2 w-2 rounded-full"}
          style={{ background: frame ? bandColor(frame.band) : "#8b9196" }}
        />
        <span className="text-2xs uppercase tracking-wide text-muted">
          {connected ? "Live" : "Offline"}
          {frame && ` · ${frame.risk.toFixed(0)}/100`}
        </span>
      </div>
    </Card>
  );
}
