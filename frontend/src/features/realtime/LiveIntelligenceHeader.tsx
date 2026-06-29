// LiveIntelligenceHeader — the at-a-glance state of the selected cell: current vs
// previous risk, the primary driver behind the move, confidence, and the Kalman
// uncertainty. Re-renders only when the stream hook commits a new frame.
import { Badge, Card, RiskScore } from "@/components/ui";
import { bandColor } from "@/utils/risk";
import type { V3Frame } from "@/types/v3";

function Trend({ risk, prev }: { risk: number; prev: number | null }) {
  if (prev == null) return <span className="text-muted">■ Awaiting</span>;
  if (risk > prev + 0.05)
    return <span style={{ color: bandColor("severe") }}>▲ Increasing</span>;
  if (risk < prev - 0.05)
    return <span style={{ color: bandColor("low") }}>▼ Decreasing</span>;
  return <span className="text-muted">■ Stable</span>;
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="eyebrow mb-0.5">{label}</div>
      <div className="text-sm font-semibold text-text">{children}</div>
    </div>
  );
}

export function LiveIntelligenceHeader({
  frame,
  connected,
}: {
  frame: V3Frame | null;
  connected: boolean;
}) {
  return (
    <Card>
      <div className="flex items-center justify-between">
        <div>
          <div className="eyebrow">Live Intelligence · Cell</div>
          <h2 className="text-glow-cyan text-lg font-bold text-accent">
            {frame?.cell ?? "—"}
            {frame && <span className="ml-2 text-2xs text-muted-2">({frame.cell_id})</span>}
          </h2>
        </div>
        <Badge tone={connected ? "success" : "muted"}>{connected ? "● live" : "offline"}</Badge>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
        <Field label="Current Risk">
          {frame ? <RiskScore score={frame.risk} band={frame.band} size="sm" /> : "—"}
        </Field>
        <Field label="Previous Risk">
          <span className="tabular-nums text-muted">
            {frame?.prev_risk != null ? `${frame.prev_risk.toFixed(0)} / 100` : "—"}
          </span>
        </Field>
        <Field label="Trend">
          <Trend risk={frame?.risk ?? 0} prev={frame?.prev_risk ?? null} />
        </Field>
        <Field label="Confidence">
          <span className="tabular-nums text-accent">
            {frame ? `${Math.round(frame.confidence * 100)}%` : "—"}
            {frame && (
              <span className="ml-1 text-2xs text-muted-2">σ²={frame.temp_variance.toFixed(2)}</span>
            )}
          </span>
        </Field>
        <Field label="Primary Driver">
          <span className="text-text">
            {frame?.driver ?? "—"}
            {frame && (
              <span className="ml-1 text-2xs text-muted-2">({frame.temp_delta >= 0 ? "+" : ""}{frame.temp_delta.toFixed(1)}°C)</span>
            )}
          </span>
        </Field>
      </div>
    </Card>
  );
}
