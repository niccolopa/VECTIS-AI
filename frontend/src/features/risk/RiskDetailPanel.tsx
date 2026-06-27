import { Link } from "react-router-dom";
import { Badge, Button, ConfidenceBar, RiskBadge, RiskScore } from "@/components/ui";
import { DriversChart } from "@/components/charts/DriversChart";
import { titleCase } from "@/utils/format";
import type { CellRisk, DecisionReport, Priority } from "@/types/api";

const PRIORITY_TONE: Record<Priority, "danger" | "warning" | "muted"> = {
  high: "danger",
  medium: "warning",
  low: "muted",
};

interface Props {
  report: DecisionReport;
  selectedCell?: CellRisk | null;
}

// The decision context for a region: score, confidence, the model's drivers, and
// recommended actions. When a map cell is selected its score/coords are surfaced
// (cells carry no driver detail — region drivers explain the picture).
export function RiskDetailPanel({ report, selectedCell }: Props) {
  return (
    <div className="flex h-full flex-col overflow-y-auto">
      <div className="border-b border-border p-4">
        <div className="flex items-start justify-between">
          <div>
            <div className="eyebrow">Area</div>
            <h3 className="text-base font-semibold">{report.area_label}</h3>
          </div>
          <div className="text-right">
            <RiskScore score={report.risk_score} band={report.risk_band} size="lg" />
            <div className="mt-1">
              <RiskBadge band={report.risk_band} />
            </div>
          </div>
        </div>
        <div className="mt-3">
          <div className="eyebrow mb-1">Confidence</div>
          <ConfidenceBar value={report.confidence} />
        </div>
      </div>

      {selectedCell && (
        <div className="border-b border-border bg-surface-2 px-4 py-2.5 text-xs">
          <span className="text-muted">Selected cell </span>
          <span className="font-mono">{selectedCell.cell_id}</span>
          <span className="text-muted"> · </span>
          <span className="font-semibold" style={{ color: "inherit" }}>
            {selectedCell.risk_score.toFixed(0)}/100
          </span>
          <span className="text-muted">
            {" "}
            @ {selectedCell.lat.toFixed(3)}, {selectedCell.lon.toFixed(3)}
          </span>
        </div>
      )}

      <div className="space-y-5 p-4">
        <section>
          <div className="eyebrow mb-1.5">AI Summary</div>
          <p className="text-sm leading-relaxed text-text/90">{report.summary}</p>
        </section>

        <section>
          <div className="eyebrow mb-1.5">Main Drivers — why</div>
          <DriversChart drivers={report.drivers} />
        </section>

        <section>
          <div className="eyebrow mb-2">Recommended Actions</div>
          <ul className="space-y-2">
            {report.recommended_actions.map((a, i) => (
              <li key={i} className="flex gap-2.5">
                <Badge tone={PRIORITY_TONE[a.priority]}>{a.priority}</Badge>
                <div>
                  <div className="text-sm font-medium">{a.action}</div>
                  <div className="text-xs text-muted">{a.rationale}</div>
                </div>
              </li>
            ))}
          </ul>
        </section>

        <div className="flex items-center justify-between border-t border-border pt-3 text-2xs text-muted-2">
          <span>
            Critic:{" "}
            <span className={report.critic_review.approved ? "text-risk-low" : "text-risk-high"}>
              {report.critic_review.approved ? "Approved" : "Needs review"}
            </span>{" "}
            · model {titleCase(report.model_card_ref.split("/")[1]?.split("@")[0] ?? "")}
          </span>
          <Link to={`/reports/${report.id}`}>
            <Button size="sm" variant="ghost">
              Full report →
            </Button>
          </Link>
        </div>
      </div>
    </div>
  );
}
