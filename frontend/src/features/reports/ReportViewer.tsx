import { useState, type ReactNode } from "react";
import { Badge, Button, Card, ConfidenceBar, RiskBadge, RiskScore } from "@/components/ui";
import { DriversChart } from "@/components/charts/DriversChart";
import { AgentTraceList } from "@/features/reports/AgentTraceList";
import { dateTime } from "@/utils/format";
import type { DecisionReport, Priority } from "@/types/api";

const PRIORITY_TONE: Record<Priority, "danger" | "warning" | "muted"> = {
  high: "danger",
  medium: "warning",
  low: "muted",
};

// Labels the three layers VECTIS keeps deliberately separate: the AI's
// interpretation, the checkable evidence behind it, and the human's decision.
function Band({ kind, children }: { kind: "ai" | "evidence" | "human"; children: ReactNode }) {
  const meta = {
    ai: { label: "AI-Generated Insight", color: "#4f8cff" },
    evidence: { label: "Supporting Evidence", color: "#9aa4b2" },
    human: { label: "Human Decision", color: "#22c55e" },
  }[kind];
  return (
    <Card flush className="overflow-visible">
      <div
        className="border-b border-border px-4 py-2 text-2xs font-semibold uppercase tracking-wider"
        style={{ color: meta.color }}
      >
        ● {meta.label}
      </div>
      <div className="p-4">{children}</div>
    </Card>
  );
}

export function ReportViewer({ report }: { report: DecisionReport }) {
  const [decision, setDecision] = useState<string | null>(null);

  return (
    <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
      <div className="space-y-4 xl:col-span-2">
        <Card>
          <div className="flex items-start justify-between">
            <div>
              <div className="eyebrow">Decision Intelligence Report</div>
              <h2 className="mt-0.5 text-xl font-semibold">{report.area_label}</h2>
              <div className="mt-1 text-xs text-muted">
                {dateTime(report.generated_at)} · {report.model_card_ref}
              </div>
            </div>
            <div className="text-right">
              <RiskScore score={report.risk_score} band={report.risk_band} size="lg" />
              <div className="mt-1">
                <RiskBadge band={report.risk_band} />
              </div>
            </div>
          </div>
          <div className="mt-3 max-w-sm">
            <div className="eyebrow mb-1">Confidence</div>
            <ConfidenceBar value={report.confidence} />
          </div>
        </Card>

        <Band kind="ai">
          <p className="text-sm leading-relaxed text-text/90">{report.summary}</p>
          <div className="mt-4">
            <div className="eyebrow mb-1.5">Drivers (SHAP attribution)</div>
            <DriversChart drivers={report.drivers} />
          </div>
        </Band>

        <Band kind="evidence">
          <ul className="space-y-2">
            {report.evidence.map((e, i) => (
              <li key={i} className="flex items-start gap-2 text-sm">
                <Badge tone="muted">{e.source}</Badge>
                <span className="text-text/90">
                  {e.statement}
                  {e.metric != null && e.value != null && (
                    <span className="text-muted">
                      {" "}
                      ({e.metric}={e.value})
                    </span>
                  )}
                </span>
              </li>
            ))}
          </ul>
        </Band>
      </div>

      <div className="space-y-4">
        <Card>
          <div className="eyebrow mb-2">Recommended Actions</div>
          <ul className="space-y-2.5">
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
        </Card>

        <Card>
          <div className="eyebrow mb-2">
            Critic Review · {report.critic_review.issues.length} finding(s)
          </div>
          <div className="mb-2 text-sm">
            {report.critic_review.approved ? (
              <span className="text-risk-low">✓ Approved — claims substantiated</span>
            ) : (
              <span className="text-risk-high">⚠ Needs review</span>
            )}
          </div>
          <p className="text-xs text-muted">{report.critic_review.notes}</p>
          {report.critic_review.issues.map((it, i) => (
            <div key={i} className="mt-2 text-xs">
              <Badge tone={it.severity === "blocker" ? "danger" : "warning"}>{it.severity}</Badge>{" "}
              <span className="text-muted">{it.problem}</span>
            </div>
          ))}
        </Card>

        <Band kind="human">
          <p className="mb-3 text-xs text-muted">
            VECTIS recommends; a human decides. (Decisions are local to this view — persistence
            is a roadmap item.)
          </p>
          <div className="flex flex-wrap gap-2">
            {(["Accept", "Override", "Defer"] as const).map((d) => (
              <Button
                key={d}
                size="sm"
                variant={decision === d ? "primary" : "secondary"}
                onClick={() => setDecision(d)}
              >
                {d}
              </Button>
            ))}
          </div>
          {decision && (
            <div className="mt-3 text-xs text-muted">
              Decision recorded: <span className="font-semibold text-text">{decision}</span>
            </div>
          )}
        </Band>

        <Card>
          <div className="eyebrow mb-2">Agent Trace · {report.trace.length} steps</div>
          <AgentTraceList trace={report.trace} />
        </Card>
      </div>
    </div>
  );
}
