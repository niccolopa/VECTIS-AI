// AiIntelligenceBrief — renders the LangGraph board's DecisionIntelligenceReport
// (Future Worlds). Structured, not a wall of text: BLUF, analyst summary, scenario
// storylines, the optimist/pessimist debate, and the red-team critique. All numbers
// here are copied from the engine (Math Firewall) — the LLM only wrote the prose.
import { Badge, Card, CardHeader } from "@/components/ui";
import { titleCase } from "@/utils/format";
import type { DecisionIntelligenceReport } from "@/types/v2";

export function AiIntelligenceBrief({ report }: { report: DecisionIntelligenceReport }) {
  return (
    <Card>
      <CardHeader
        eyebrow={report.classification}
        title="AI Decision Intelligence Brief"
        actions={<Badge tone="accent">{report.report_id}</Badge>}
      />

      <div className="mt-3 border-l-2 border-accent/50 pl-3">
        <div className="eyebrow">Bottom line</div>
        <p className="text-sm text-text">{report.bottom_line}</p>
      </div>

      <div className="mt-4">
        <div className="eyebrow mb-1">Analyst</div>
        <p className="text-sm text-muted">{report.analyst.summary}</p>
      </div>

      <div className="mt-4">
        <div className="eyebrow mb-1">Scenario storylines</div>
        <ul className="space-y-2">
          {report.scenarios.map((s) => (
            <li key={s.scenario_id} className="text-sm">
              <span className="font-medium">{titleCase(s.name)}</span>{" "}
              <span className="text-muted-2">({s.probability_pct.toFixed(0)}%)</span>
              <p className="text-muted">{s.storyline}</p>
            </li>
          ))}
        </ul>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div className="rounded border border-risk-low/30 bg-risk-low/5 p-2">
          <div className="eyebrow mb-1 text-risk-low">Optimist</div>
          <p className="text-xs text-muted">{report.debate.optimist_case}</p>
        </div>
        <div className="rounded border border-risk-severe/30 bg-risk-severe/5 p-2">
          <div className="eyebrow mb-1 text-risk-severe">Pessimist</div>
          <p className="text-xs text-muted">{report.debate.pessimist_case}</p>
        </div>
      </div>

      <div className="mt-4">
        <div className="flex items-center justify-between">
          <div className="eyebrow">Red team</div>
          <Badge tone="warning">
            {report.red_team.residual_uncertainty_pct.toFixed(0)}% residual
          </Badge>
        </div>
        <p className="mt-1 text-sm text-muted">{report.red_team.challenge}</p>
        {report.red_team.blind_spots.length > 0 && (
          <ul className="mt-2 list-disc pl-5 text-xs text-muted-2">
            {report.red_team.blind_spots.map((b) => (
              <li key={b}>{b}</li>
            ))}
          </ul>
        )}
      </div>
    </Card>
  );
}
