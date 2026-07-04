// DashboardPage (V2) — the Simulation & Forecasting command center. Composes the
// four V2 features over one twin: live risk headline, Scenario Explorer, Probability
// Timeline (fed by the WebSocket stream), What-If simulator, and the AI brief.
import { PageContainer, PageHeader } from "@/components/layout/Page";
import { Badge, ErrorState, LoadingState, RiskScore } from "@/components/ui";
import { AiIntelligenceBrief } from "@/features/dashboard/AiIntelligenceBrief";
import { ProbabilityTimeline } from "@/features/dashboard/ProbabilityTimeline";
import { ScenarioExplorer } from "@/features/dashboard/ScenarioExplorer";
import { WhatIfSimulator } from "@/features/dashboard/WhatIfSimulator";
import { useTwinView } from "@/hooks/dashboardQueries";
import { useTwinStream } from "@/hooks/useTwinStream";

const TWIN_ID = "california"; // ponytail: single twin for now; add a picker via useTwins() when >1.

export function DashboardPage() {
  const { data: view, isLoading, isError, error } = useTwinView(TWIN_ID);
  // Stream seeds the timeline with the current risk, then appends live updates.
  const { timeline, connected, latest } = useTwinStream(TWIN_ID, view?.risk);

  if (isLoading) return <PageContainerLoading />;
  if (isError || !view)
    return (
      <PageContainer>
        <PageHeader title="Decision Intelligence" subtitle="V2 simulation & forecasting" />
        <ErrorState message={(error as Error)?.message ?? "Failed to load twin."} />
      </PageContainer>
    );

  // Prefer the freshest risk from the stream if an update has arrived.
  const liveRisk = latest?.risk ?? view.risk;

  return (
    <PageContainer>
      <PageHeader
        title="Decision Intelligence"
        subtitle={`Digital twin: ${view.twin_id} · ${view.scenarios.length} scenario branches`}
        actions={
          <div className="flex items-center gap-3">
            <RiskScore score={liveRisk.risk} band={liveRisk.band} size="sm" />
            <Badge tone="muted">{Math.round(liveRisk.confidence * 100)}% confidence</Badge>
            <Badge tone={connected ? "success" : "muted"}>{connected ? "● live" : "offline"}</Badge>
          </div>
        }
      />

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <div className="space-y-4 xl:col-span-2">
          <ScenarioExplorer scenarios={view.scenarios} risk={liveRisk} />
          <ProbabilityTimeline points={timeline} live={connected} />
          <AiIntelligenceBrief report={view.report} />
        </div>
        <div className="xl:col-span-1">
          <WhatIfSimulator twinId={view.twin_id} baseState={view.state} baseRisk={view.risk} />
        </div>
      </div>
    </PageContainer>
  );
}

function PageContainerLoading() {
  return (
    <PageContainer>
      <PageHeader title="Decision Intelligence" subtitle="V2 simulation & forecasting" />
      <LoadingState />
    </PageContainer>
  );
}
