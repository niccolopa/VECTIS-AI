// WhatIfSimulator — the Simulation Center. Manual sliders perturb the twin's state
// (temperature, humidity, vegetation stress, recent fires); "Run" calls the
// synchronous What-If endpoint (S13-cached) and shows the recomputed RiskState plus
// the delta vs. the twin's current risk. Numbers are seeded + cached, so the same
// slider positions return instantly and identically.
import { useState } from "react";

import { Badge, Button, Card, CardHeader, RiskScore } from "@/components/ui";
import { useWhatIf } from "@/hooks/dashboardQueries";
import type { RegionState, RiskState } from "@/types/v2";

interface SliderSpec {
  key: keyof RegionState;
  label: string;
  min: number;
  max: number;
  step: number;
  unit: string;
}

const SLIDERS: SliderSpec[] = [
  { key: "temperature_anomaly", label: "Temperature anomaly", min: 0, max: 8, step: 0.5, unit: "°C" },
  { key: "humidity_level", label: "Humidity", min: 0, max: 100, step: 5, unit: "%" },
  { key: "vegetation_stress", label: "Vegetation stress", min: 0, max: 100, step: 5, unit: "" },
  { key: "recent_fire_history", label: "Recent fires", min: 0, max: 10, step: 1, unit: "" },
];

export function WhatIfSimulator({
  twinId,
  baseState,
  baseRisk,
}: {
  twinId: string;
  baseState: RegionState;
  baseRisk: RiskState;
}) {
  const [state, setState] = useState<RegionState>(baseState);
  const whatIf = useWhatIf();
  const result = whatIf.data;

  const run = () => whatIf.mutate({ twin_id: twinId, overrides: state });
  const reset = () => {
    setState(baseState);
    whatIf.reset();
  };

  const delta = result ? result.risk.risk - baseRisk.risk : 0;

  return (
    <Card>
      <CardHeader
        eyebrow="Simulation Center"
        title="What-If simulator"
        actions={
          <Badge tone="accent">{whatIf.isPending ? "running…" : "synchronous"}</Badge>
        }
      />

      <div className="mt-3 space-y-3">
        {SLIDERS.map((s) => (
          <label key={s.key} className="block text-xs text-muted">
            {s.label}:{" "}
            <span className="text-text tabular-nums">
              {state[s.key]}
              {s.unit}
            </span>
            <input
              type="range"
              min={s.min}
              max={s.max}
              step={s.step}
              value={state[s.key]}
              onChange={(e) => setState((p) => ({ ...p, [s.key]: Number(e.target.value) }))}
              className="mt-1 w-full accent-accent"
            />
          </label>
        ))}
      </div>

      <div className="mt-4 flex gap-2">
        <Button
          className="flex-1"
          variant="primary"
          onClick={run}
          loading={whatIf.isPending}
        >
          Run simulation
        </Button>
        <Button className="flex-1" variant="ghost" onClick={reset} disabled={whatIf.isPending}>
          Reset
        </Button>
      </div>

      {whatIf.isError && (
        <p className="mt-3 text-xs text-risk-severe">
          Simulation failed: {(whatIf.error as Error).message}
        </p>
      )}

      {result && (
        <div className="mt-4 border-t border-border pt-3">
          <div className="flex items-center justify-between">
            <div>
              <div className="eyebrow mb-1">Projected risk</div>
              <RiskScore score={result.risk.risk} band={result.risk.band} size="md" />
            </div>
            <Badge tone={delta > 0 ? "danger" : delta < 0 ? "success" : "muted"}>
              {delta > 0 ? "+" : ""}
              {delta.toFixed(1)} vs current
            </Badge>
          </div>
          <div className="mt-3 space-y-1">
            {result.scenarios.map((s) => (
              <div key={s.id} className="flex justify-between text-xs">
                <span className="text-muted">{s.name}</span>
                <span className="tabular-nums">
                  {s.risk.p05.toFixed(0)}–{s.risk.p95.toFixed(0)} (μ {s.risk.mean.toFixed(0)})
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </Card>
  );
}
