// Belief-history types — 1:1 with the backend Pydantic schemas.
// Source of truth: vectis/api/routers/history.py → CellHistory / PlaybackResponse.
// These are recorded moments (illustrative, uncalibrated coefficients); replay shows
// what the system *believed* at a past instant, never validated ground truth.

/** One recorded moment of one cell's risk × confidence × belief. */
export interface HistoryPoint {
  ts: string;
  risk: number;
  confidence: number;
  tier: string;
  trigger: string;
  hazard: string;
  posterior: Record<string, number>;
  report_id: string | null;
}

export interface CellHistory {
  cell_id: string;
  points: HistoryPoint[];
}

/** One time-slice of the map: every snapshotted cell's latest state as of `ts`. */
export interface FrameCell {
  cell_id: string;
  lat: number;
  lon: number;
  risk: number;
  confidence: number;
  hazard: string;
}

export interface PlaybackFrame {
  ts: string;
  cells: FrameCell[];
}

export interface PlaybackResponse {
  start: string;
  end: string;
  frames: PlaybackFrame[];
}
