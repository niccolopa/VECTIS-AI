// Global terminal stream types — 1:1 with the SSE frames the backend emits.
// Source of truth on the server: vectis/api/routers/live.py → terminal_frame.

import type { RiskBand } from "@/types/api";

/** A normalized observation, display-ready for the rolling event feed. */
export interface V3Event {
  event_id: string;
  source: string;
  variable: string;
  value: number;
  observed_at: string; // ISO
  /** Whether this event was genuinely fetched live or is a synthetic fallback
   * (Session 41). Optional so older frames/fixtures still type-check; absent is
   * treated as unlabeled, not asserted live. */
  data_source?: import("@/types/connectors").DataSource;
}

/** One tick of the viewport-scoped terminal stream (Session 37).
 * Source of truth: vectis/api/routers/live.py → terminal_frame.
 * `cells` is the viewport's Tier-0 screened view; `events` is the *global* tape.
 * The headline trio (risk/band/cell_id) is null when nothing screened is visible —
 * an honest absence, never a fabricated zero. */
export interface TerminalFrame {
  tick: number;
  ts: string; // ISO
  scope: { west: number; south: number; east: number; north: number; zoom: number };
  resolution: number;
  cells: import("@/types/tiles").TileCell[];
  events: V3Event[];
  risk: number | null; // hottest screened score in the viewport, 0–100
  band: RiskBand | null;
  cell_id: string | null; // the cell carrying that hottest score
}
