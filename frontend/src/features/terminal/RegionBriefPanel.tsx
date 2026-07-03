// RegionBriefPanel — the drill-down. Click any cell on the world map and get the
// full picture of what VECTIS actually knows about it, at the depth that truly
// exists for it:
//
//   T0 — screened only. The panel leads with an explicit "screening estimate only"
//        notice and renders flat per-hazard score bars — deliberately NOT the
//        box-and-whisker treatment, because a Tier-0 point estimate has no
//        distribution and is measured biased low in the mid-band (Session 32).
//   T1 — a real Monte Carlo + Bayesian forecast: per-scenario p05/p50/p95 whiskers
//        (the V2 ScenarioExplorer, reused) and the Bayesian posterior (Session-24
//        ProbabilityBars, reused).
//   T2 — the analyst board's intelligence brief rides the analysis
//        (AiIntelligenceBrief, reused).
import { useQuery } from "@tanstack/react-query";

import { Badge, Card, CardHeader } from "@/components/ui";
import { AiIntelligenceBrief } from "@/features/dashboard/AiIntelligenceBrief";
import { ScenarioExplorer } from "@/features/dashboard/ScenarioExplorer";
import { ProbabilityBars } from "@/features/realtime/ProbabilityBars";
import { HAZARD_META } from "@/features/terminal/HazardToggle";
import { fetchCellBrief } from "@/services/cells";
import { qk } from "@/services/queryKeys";
import type { CellBrief } from "@/types/cells";
import type { Hazard } from "@/types/tiles";
import type { RiskState, ScenarioProjection } from "@/types/v2";
import { riskColor } from "@/utils/risk";

const TIER_LABEL: Record<CellBrief["tier"], string> = {
  T0: "T0 · screened only",
  T1: "T1 · full analysis",
  T2: "T2 · board report",
};

/** Flat per-hazard screening bars — a point estimate, not a distribution. */
function ScreeningBars({ screening }: { screening: Record<string, number> }) {
  const rows = Object.entries(screening).sort(([, a], [, b]) => b - a);
  if (rows.length === 0) {
    return <div className="text-xs text-muted-2">No hazard has an observed driver here.</div>;
  }
  return (
    <div className="space-y-2">
      {rows.map(([hazard, score]) => {
        const meta = HAZARD_META[hazard as Hazard] ?? { label: hazard, color: "#8b9196" };
        return (
          <div key={hazard}>
            <div className="mb-1 flex items-center justify-between text-xs">
              <span style={{ color: meta.color }}>{meta.label}</span>
              <span className="tabular-nums" style={{ color: riskColor(score) }}>
                {score.toFixed(0)}
              </span>
            </div>
            <div className="h-1.5 w-full overflow-hidden rounded-full bg-surface-3">
              <div
                className="h-full rounded-full"
                style={{ width: `${Math.min(100, score)}%`, background: riskColor(score) }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}

function toExplorerProps(brief: CellBrief): { scenarios: ScenarioProjection[]; risk: RiskState } {
  const analysis = brief.analysis!;
  return {
    scenarios: analysis.scenarios.map((s) => ({
      id: s.id,
      name: s.id.replace(/_/g, " "),
      description: "",
      probability: s.probability,
      expected_band: s.expected_band,
      risk: s.risk,
    })),
    risk: {
      region: brief.cell_id,
      risk: analysis.risk,
      band: analysis.band,
      confidence: analysis.confidence,
      scenario_priors: analysis.posterior,
      updated_at: brief.state?.last_updated ?? "",
    },
  };
}

export function RegionBriefPanel({
  cellId,
  pinned,
  onTogglePin,
  onClose,
}: {
  cellId: string;
  pinned: boolean;
  onTogglePin: (brief: CellBrief) => void;
  onClose: () => void;
}) {
  const query = useQuery({
    queryKey: qk.cellBrief(cellId),
    queryFn: () => fetchCellBrief(cellId),
  });
  const brief = query.data;

  return (
    <div className="flex h-full flex-col gap-3 overflow-y-auto" data-testid="region-brief">
      <Card>
        <CardHeader
          eyebrow="Region Brief"
          title={`Cell ${cellId}`}
          actions={
            <div className="flex items-center gap-2">
              {brief && <Badge tone={brief.tier === "T0" ? "warning" : "accent"}>{TIER_LABEL[brief.tier]}</Badge>}
              {brief && (
                <button
                  type="button"
                  onClick={() => onTogglePin(brief)}
                  className="rounded border border-border-strong px-2 py-0.5 text-2xs uppercase tracking-wide text-muted hover:text-text"
                >
                  {pinned ? "★ Unpin" : "☆ Pin"}
                </button>
              )}
              <button
                type="button"
                onClick={onClose}
                aria-label="Close brief"
                className="rounded border border-border-strong px-2 py-0.5 text-2xs text-muted hover:text-text"
              >
                ✕
              </button>
            </div>
          }
        />
        {brief && (
          <p className="mt-1 text-2xs tabular-nums text-muted-2">
            {brief.lat.toFixed(3)}, {brief.lon.toFixed(3)}
            {brief.state && ` · v${brief.state.version} · ${brief.state.sources.join(", ")}`}
            {brief.source_cells > 1 &&
              ` · aggregates ${brief.source_cells} native cells (max per hazard)`}
          </p>
        )}
        {query.isLoading && <p className="mt-3 text-xs text-muted-2">Loading brief…</p>}
        {query.isError && (
          <p className="mt-3 text-xs text-muted-2">
            No observed state for this cell yet — nothing honest to show.
          </p>
        )}
      </Card>

      {brief && brief.tier === "T0" && (
        <>
          <Card className="border-risk-high/40 bg-risk-high/5">
            <div className="eyebrow text-risk-high">Screening estimate only</div>
            <p className="mt-1 text-xs text-muted">
              This cell has only passed the cheap Tier-0 screen — a single vectorized point
              estimate per hazard. It has <span className="text-text">not</span> been promoted
              to full Monte Carlo analysis, and the screen is a biased approximation
              (measured up to ~13 pts low in the mid-risk band). Treat these numbers as a
              flag to look closer, not a forecast.
            </p>
          </Card>
          <Card>
            <CardHeader eyebrow="Tier 0" title="Per-hazard screening scores" />
            <div className="mt-3">
              <ScreeningBars screening={brief.screening} />
            </div>
          </Card>
        </>
      )}

      {brief && brief.analysis && (
        <>
          <ScenarioExplorer {...toExplorerProps(brief)} />
          <ProbabilityBars posterior={brief.analysis.posterior} />
          {Object.keys(brief.screening).length > 0 && (
            <Card>
              <CardHeader eyebrow="Tier 0 · for comparison" title="Screening scores" />
              <div className="mt-3">
                <ScreeningBars screening={brief.screening} />
              </div>
            </Card>
          )}
          {brief.analysis.report && <AiIntelligenceBrief report={brief.analysis.report} />}
        </>
      )}
    </div>
  );
}
