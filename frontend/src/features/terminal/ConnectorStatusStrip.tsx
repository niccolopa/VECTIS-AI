// Live/Synthetic transparency (Session 41) — the terminal must never let an operator
// mistake offline synthetic fallback for live global data.
//
//   · ConnectorBadges — a persistent per-feed cluster (Fire/Quake/Multi-hazard/Weather),
//     each stamped LIVE or SYNTHETIC from the feed's real last poll, with the same visual
//     rigor as the T0/T1/T2 and live/replay distinctions.
//   · SyntheticDemoBanner — the single unmistakable top-level state for the zero-credential
//     fresh clone: when EVERY feed is synthetic, one banner says so, so a first-time user
//     understands what they're looking at without having to read four small badges.
//
// Both read one polled endpoint (GET /api/v1/connectors) — never a hardcoded assumption.
import { useQuery } from "@tanstack/react-query";

import { fetchConnectorStatus } from "@/services/connectors";
import { qk } from "@/services/queryKeys";
import type { ConnectorStatus, ConnectorStatusResponse } from "@/types/connectors";

export function useConnectorStatus() {
  return useQuery<ConnectorStatusResponse>({
    queryKey: qk.connectorStatus,
    queryFn: fetchConnectorStatus,
    refetchInterval: 30_000, // matches the ingestion tick — status can flip if a feed drops
  });
}

function FeedBadge({ c }: { c: ConnectorStatus }) {
  const live = c.data_source === "live";
  return (
    <span
      data-testid={`connector-badge-${c.source}`}
      data-state={c.data_source}
      title={
        live
          ? `${c.label}: genuinely fetching live data`
          : `${c.label}: running on offline synthetic fallback (no live fetch)`
      }
      // shrink-0 + nowrap: a squeezed strip must never wrap a label ("MULTI-HAZARD"
      // broke at its hyphen into a two-line box, unlike its three siblings).
      className={`flex shrink-0 items-center gap-1 whitespace-nowrap rounded border px-1.5 py-0.5 text-2xs font-semibold uppercase tracking-wide ${
        live
          ? "border-emerald-500/50 bg-emerald-500/10 text-emerald-400"
          : "border-risk-high/60 bg-risk-high/10 text-risk-high"
      }`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${live ? "bg-emerald-400" : "bg-risk-high"}`} />
      {c.label}
      <span className="opacity-80">{live ? "LIVE" : "SYNTHETIC"}</span>
    </span>
  );
}

/** The persistent per-connector cluster shown in the terminal's top strip. */
export function ConnectorBadges() {
  const { data } = useConnectorStatus();
  if (!data || data.connectors.length === 0) return null;
  return (
    <div data-testid="connector-badges" className="flex items-center gap-1.5">
      {data.connectors.map((c) => (
        <FeedBadge key={c.source} c={c} />
      ))}
    </div>
  );
}

/** The single top-level banner — rendered iff EVERY feed is synthetic. */
export function SyntheticDemoBanner() {
  const { data } = useConnectorStatus();
  if (!data || !data.all_synthetic) return null;
  return (
    <div
      data-testid="synthetic-demo-banner"
      role="status"
      className="flex items-center justify-center gap-2 border-b border-risk-high bg-risk-high/15 px-4 py-1.5 text-xs font-semibold tracking-wide text-risk-high"
    >
      <span className="text-sm">⚠</span>
      FULL SYNTHETIC DEMO — no live API credentials configured. Every feed is running on
      offline fallback data; this is a demonstration of VECTIS, not live global data.
    </div>
  );
}
