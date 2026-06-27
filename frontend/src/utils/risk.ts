// Risk → color mapping, the single source shared by the map ramp, badges, and
// charts so the visual language is consistent across the console. Values match
// the Tailwind `risk.*` tokens in tailwind.config.js.
import type { RiskBand } from "@/types/api";

export const RISK_COLORS = {
  low: "#22c55e",
  moderate: "#eab308",
  high: "#f59e0b",
  severe: "#ef4444",
} as const;

export function bandFromScore(score: number): RiskBand {
  if (score >= 75) return "severe";
  if (score >= 50) return "high";
  if (score >= 25) return "moderate";
  return "low";
}

export function riskColor(score: number): string {
  return RISK_COLORS[bandFromScore(score)];
}

export function bandColor(band: RiskBand): string {
  return RISK_COLORS[band];
}

export function bandLabel(band: RiskBand): string {
  return band.charAt(0).toUpperCase() + band.slice(1);
}

/** MapLibre data-driven color ramp for the per-cell risk layer. */
export function mapRiskRamp(): unknown[] {
  return [
    "interpolate",
    ["linear"],
    ["get", "risk"],
    0,
    "#22c55e",
    25,
    "#eab308",
    50,
    "#f59e0b",
    75,
    "#ef4444",
    100,
    "#b91c1c",
  ];
}
