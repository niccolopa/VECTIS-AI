import { useState } from "react";
import { Badge, Button, Card } from "@/components/ui";
import { scenariosFromReport } from "@/services/analyses";
import { titleCase } from "@/utils/format";
import { bandFromScore, riskColor } from "@/utils/risk";
import { RiskBadge } from "@/components/ui/risk";
import type { DecisionReport } from "@/types/api";

// Real what-if results come from the backend Simulation agent (read off the
// report trace). The custom-scenario builder is architecture-only: the backend
// does not yet accept custom perturbation parameters (Session 5).
export function ScenarioPanel({ report }: { report: DecisionReport }) {
  const scenarios = scenariosFromReport(report);
  const baseline = report.risk_score;

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
      <div className="space-y-3 lg:col-span-2">
        <Card>
          <div className="eyebrow mb-1">Baseline</div>
          <div className="flex items-center gap-3">
            <span className="text-2xl font-bold" style={{ color: riskColor(baseline) }}>
              {baseline.toFixed(0)}/100
            </span>
            <RiskBadge band={report.risk_band} />
            <span className="text-xs text-muted">{report.area_label}</span>
          </div>
        </Card>

        <div className="space-y-2">
          {scenarios.length === 0 && (
            <Card>
              <p className="text-sm text-muted">No scenarios in this analysis.</p>
            </Card>
          )}
          {scenarios.map((s) => {
            const up = s.delta > 0;
            return (
              <Card key={s.name}>
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-sm font-medium">{titleCase(s.name)}</div>
                    <div className="text-xs text-muted">Projected modeled risk</div>
                  </div>
                  <div className="flex items-center gap-3">
                    <span
                      className="text-xl font-bold tabular-nums"
                      style={{ color: riskColor(s.risk_score) }}
                    >
                      {s.risk_score.toFixed(0)}
                    </span>
                    <Badge tone={up ? "danger" : "success"}>
                      {up ? "+" : ""}
                      {s.delta.toFixed(1)}
                    </Badge>
                  </div>
                </div>
                {/* delta bar relative to baseline */}
                <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-surface-3">
                  <div
                    className="h-full rounded-full"
                    style={{
                      width: `${Math.min(100, s.risk_score)}%`,
                      background: riskColor(s.risk_score),
                    }}
                  />
                </div>
                <div className="mt-1 text-2xs text-muted-2">
                  band: {bandFromScore(s.risk_score)}
                </div>
              </Card>
            );
          })}
        </div>
      </div>

      <CustomScenarioBuilder />
    </div>
  );
}

function CustomScenarioBuilder() {
  const [temp, setTemp] = useState(3);
  const [drought, setDrought] = useState(0.1);

  return (
    <Card>
      <div className="flex items-center justify-between">
        <div className="eyebrow">Custom Scenario</div>
        <Badge tone="warning">Preview</Badge>
      </div>
      <p className="mt-1 mb-3 text-xs text-muted">
        Define a perturbation and project impact. Backend support for custom parameters is a
        Session 5 task — controls are wired but disabled.
      </p>
      <label className="block text-xs text-muted">
        Temperature anomaly: <span className="text-text">+{temp.toFixed(1)}°C</span>
        <input
          type="range"
          min={0}
          max={6}
          step={0.5}
          value={temp}
          onChange={(e) => setTemp(Number(e.target.value))}
          className="mt-1 w-full accent-accent"
        />
      </label>
      <label className="mt-3 block text-xs text-muted">
        Drought index: <span className="text-text">+{drought.toFixed(2)}</span>
        <input
          type="range"
          min={0}
          max={0.5}
          step={0.05}
          value={drought}
          onChange={(e) => setDrought(Number(e.target.value))}
          className="mt-1 w-full accent-accent"
        />
      </label>
      <Button className="mt-4 w-full" disabled title="Backend support coming in Session 5">
        Run scenario (coming soon)
      </Button>
    </Card>
  );
}
