// ScenarioExplorer — visualizes each simulation branch (Baseline, Hotter & Drier,
// Extreme Wind) as a box-and-whisker on the shared 0–100 risk scale, using the
// per-scenario percentiles the dashboard API returns. The whisker spans p05–p95,
// the box marks the interquartile feel (p05→p50→p95), and the dot is the mean.
import { Badge, Card, CardHeader, RiskBadge } from "@/components/ui";
import { titleCase } from "@/utils/format";
import { bandColor, riskColor } from "@/utils/risk";
import type { ProbabilityDistribution, RiskState, ScenarioProjection } from "@/types/v2";

function Whisker({ d }: { d: ProbabilityDistribution }) {
  const pct = (v: number) => `${Math.max(0, Math.min(100, v))}%`;
  return (
    <div className="relative mt-2 h-6">
      {/* baseline track */}
      <div className="absolute top-1/2 h-px w-full -translate-y-1/2 bg-surface-3" />
      {/* p05–p95 whisker */}
      <div
        className="absolute top-1/2 h-1.5 -translate-y-1/2 rounded-full"
        style={{ left: pct(d.p05), width: pct(d.p95 - d.p05), background: `${riskColor(d.p50)}55` }}
      />
      {/* p50 median marker */}
      <div
        className="absolute top-1/2 h-4 w-0.5 -translate-y-1/2"
        style={{ left: pct(d.p50), background: riskColor(d.p50) }}
      />
      {/* mean dot */}
      <div
        className="absolute top-1/2 h-2.5 w-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full border border-bg"
        style={{ left: pct(d.mean), background: riskColor(d.mean) }}
        title={`mean ${d.mean.toFixed(1)}`}
      />
    </div>
  );
}

export function ScenarioExplorer({
  scenarios,
  risk,
}: {
  scenarios: ScenarioProjection[];
  risk: RiskState;
}) {
  return (
    <Card>
      <CardHeader
        eyebrow="Scenario Explorer"
        title="Branch outcome distributions"
        actions={<RiskBadge band={risk.band} />}
      />
      <p className="mt-1 text-xs text-muted">
        Box-and-whisker per branch on the 0–100 risk scale · whisker = p05–p95 · line = median ·
        dot = mean. Branch weight is the current posterior belief.
      </p>

      <div className="mt-4 space-y-4">
        {scenarios.map((s) => (
          <div key={s.id}>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium">{titleCase(s.name)}</span>
                <RiskBadge band={s.expected_band} />
              </div>
              <div className="flex items-center gap-2">
                <Badge tone="muted">{Math.round(s.probability * 100)}% weight</Badge>
                <span
                  className="text-sm font-bold tabular-nums"
                  style={{ color: bandColor(s.expected_band) }}
                >
                  {s.risk.mean.toFixed(0)}
                </span>
              </div>
            </div>
            <Whisker d={s.risk} />
            <div className="mt-1 flex justify-between text-2xs tabular-nums text-muted-2">
              <span>p05 {s.risk.p05.toFixed(0)}</span>
              <span>p50 {s.risk.p50.toFixed(0)}</span>
              <span>p95 {s.risk.p95.toFixed(0)}</span>
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}
