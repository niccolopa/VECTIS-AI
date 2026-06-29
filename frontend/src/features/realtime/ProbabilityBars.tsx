// ProbabilityBars — the shifting Bayesian posterior over scenarios. Plain CSS bars
// (not a chart lib): a width transition animates the belief swinging from baseline to
// hotter_drier far more smoothly than re-rendering a Recharts bar on every frame.
import { Card, CardHeader } from "@/components/ui";

// Human label + accent per scenario branch (matches the backend scenario ids).
const SCENARIOS: Record<string, { label: string; color: string }> = {
  baseline: { label: "Baseline", color: "#22c55e" },
  hotter_drier: { label: "Hotter / Drier", color: "#ef4444" },
  extreme_wind: { label: "Extreme Wind", color: "#f59e0b" },
};

export function ProbabilityBars({ posterior }: { posterior: Record<string, number> }) {
  const rows = Object.entries(posterior).sort(([, a], [, b]) => b - a);

  return (
    <Card>
      <CardHeader eyebrow="Bayesian Posterior" title="Scenario probabilities" />
      <div className="mt-3 space-y-3">
        {rows.length === 0 && (
          <div className="text-xs text-muted-2">Awaiting the live stream…</div>
        )}
        {rows.map(([id, prob]) => {
          const meta = SCENARIOS[id] ?? { label: id, color: "#8b9196" };
          const pct = Math.round(prob * 100);
          return (
            <div key={id}>
              <div className="mb-1 flex items-center justify-between text-xs">
                <span className="text-text">{meta.label}</span>
                <span className="tabular-nums text-muted">{pct}%</span>
              </div>
              <div className="h-2.5 w-full overflow-hidden rounded-full bg-surface-3">
                <div
                  className="h-full rounded-full transition-[width] duration-500 ease-out"
                  style={{ width: `${pct}%`, background: meta.color }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
}
