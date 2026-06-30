// LiveRiskMap — the global operational picture. Plots the worldwide active-fire
// hotspots the live FIRMS feed reports each tick on a real world basemap, each dot
// coloured by its fire-radiative-power, plus the headline cell coloured by the live
// posterior-weighted risk. A pulsing "LIVE" badge overlays it while connected.
import { Card } from "@/components/ui";
import { RiskMap } from "@/components/map/RiskMap";
import { WORLD, WORLD_ZOOM } from "@/components/map/world";
import { bandColor } from "@/utils/risk";
import type { CellRisk } from "@/types/api";
import type { V3Frame } from "@/types/v3";

// FRP (fire radiative power) → a 0–100 colour scale for the dot. Saturates at ~60 MW.
const frpToRisk = (frp: number) => Math.max(8, Math.min(100, frp * 1.6));

function cellsFromFrame(frame: V3Frame | null): CellRisk[] {
  if (!frame) return [];
  const hotspots = (frame.hotspots ?? []).map((h) => ({
    cell_id: `${h.place || `${h.lat},${h.lon}`}`,
    lat: h.lat,
    lon: h.lon,
    risk_score: frpToRisk(h.frp),
  }));
  // Headline cell, coloured by the live risk (overrides its hotspot if co-located).
  const [lat, lon] = frame.cell_id.split(",").map(Number);
  if (Number.isFinite(lat) && Number.isFinite(lon)) {
    hotspots.push({ cell_id: frame.cell_id, lat, lon, risk_score: frame.risk });
  }
  return hotspots;
}

export function LiveRiskMap({ frame, connected }: { frame: V3Frame | null; connected: boolean }) {
  const cells = cellsFromFrame(frame);
  const count = frame?.hotspots?.length ?? 0;
  return (
    <Card flush className="relative h-[450px]">
      <RiskMap region={WORLD} cells={cells} zoom={WORLD_ZOOM} />
      <div className="pointer-events-none absolute left-3 top-3 z-10 flex items-center gap-2 rounded-full border border-border-strong bg-bg/70 px-2 py-1 backdrop-blur">
        <span
          className={connected ? "h-2 w-2 rounded-full animate-pulse" : "h-2 w-2 rounded-full"}
          style={{ background: frame ? bandColor(frame.band) : "#8b9196" }}
        />
        <span className="text-2xs uppercase tracking-wide text-muted">
          {connected ? "Live" : "Offline"}
          {count > 0 && ` · ${count} active hotspots`}
        </span>
      </div>
    </Card>
  );
}
