import { Badge } from "@/components/ui";
import { titleCase } from "@/utils/format";
import type { AgentTrace } from "@/types/api";

// The ordered, auditable record of which agent did what — the provenance behind
// the report. Shows timing and whether the LLM was used to phrase the step.
export function AgentTraceList({ trace }: { trace: AgentTrace[] }) {
  return (
    <ol className="space-y-2.5">
      {trace.map((t, i) => (
        <li key={i} className="border-l-2 border-border pl-3">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium">{titleCase(t.agent)}</span>
            <span className="text-2xs text-muted-2">{t.duration_ms.toFixed(0)}ms</span>
            {t.used_llm && <Badge tone="accent">LLM</Badge>}
          </div>
          <p className="mt-0.5 text-xs text-muted">{t.summary}</p>
        </li>
      ))}
    </ol>
  );
}
