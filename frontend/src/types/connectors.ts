// Per-connector live-vs-synthetic status — 1:1 with the backend Pydantic schemas.
// Source of truth: vectis/api/routers/connectors.py → ConnectorStatusResponse.
//
// This is the terminal's transparency contract: which of the four planetary feeds
// (Fire / Quake / Multi-hazard / Weather) is genuinely live right now vs running on
// offline synthetic fallback, plus the aggregate flags that drive the all-synthetic banner.

export type DataSource = "live" | "synthetic_fallback";

export interface ConnectorStatus {
  source: string; // stable feed id, e.g. "nasa_firms"
  label: string; // short hazard label, e.g. "Fire"
  data_source: DataSource;
}

export interface ConnectorStatusResponse {
  connectors: ConnectorStatus[];
  /** True iff EVERY feed is synthetic — the zero-credential fresh-clone case. */
  all_synthetic: boolean;
  any_live: boolean;
}
