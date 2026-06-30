// V3 (Continuous Intelligence Engine) types — 1:1 with the live-stream frame the
// backend emits over SSE. Source of truth on the server:
//   - vectis/realtime/live_stream.py  → LiveClimateStream._frame (the frame dict)
// Each frame is one tick of the continuous pipeline: a new posterior-weighted risk,
// the Kalman state behind it, the raw events that drove it, and — when the decision
// board re-convened — the fresh report.

import type { RiskBand } from "@/types/api";
import type { DecisionIntelligenceReport } from "@/types/v2";

/** A normalized observation, display-ready for the rolling event feed. */
export interface V3Event {
  event_id: string;
  source: string;
  variable: string;
  value: number;
  observed_at: string; // ISO
}

/** A worldwide active-fire detection (FIRMS) for the global map. */
export interface V3Hotspot {
  lat: number;
  lon: number;
  frp: number; // fire radiative power
  place: string; // human label, e.g. "California, US"
}

/** One tick of the continuous pipeline. */
export interface V3Frame {
  tick: number;
  cell: string; // friendly label, e.g. "Liguria_01"
  cell_id: string; // grid key, e.g. "44.4,8.9"
  ts: string; // ISO frame timestamp
  risk: number; // 0–100
  prev_risk: number | null;
  band: RiskBand;
  confidence: number; // 0–1
  driver: string; // human label for the dominant scenario
  temp_mean: number; // Kalman temperature estimate
  temp_variance: number; // Kalman uncertainty (variance)
  temp_delta: number; // change vs previous tick
  posterior: Record<string, number>; // scenario id → probability (sums to 1)
  events: V3Event[]; // raw events that drove this tick
  hotspots: V3Hotspot[]; // worldwide active-fire detections this tick
  report_id: string | null;
  report: DecisionIntelligenceReport | null; // present only when freshly generated
}

/** A point on the risk-evolution timeline, accumulated client-side from the stream. */
export interface V3TimelinePoint {
  t: string; // ISO
  risk: number; // 0–100
  confidence: number; // 0–1
  band: RiskBand;
}
