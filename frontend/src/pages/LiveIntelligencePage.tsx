// LiveIntelligencePage — the V3 Continuous Intelligence console. Subscribes once to
// the SSE stream via useV3Stream and lays the five real-time components over a single
// connection: header, live map, risk-evolution timeline, posterior bars, event feed.
// All animation is driven by the stream — no polling, no refetch.
import { PageContainer, PageHeader } from "@/components/layout/Page";
import { Badge } from "@/components/ui";
import { EventFeed } from "@/features/realtime/EventFeed";
import { LiveIntelligenceHeader } from "@/features/realtime/LiveIntelligenceHeader";
import { LiveRiskMap } from "@/features/realtime/LiveRiskMap";
import { ProbabilityBars } from "@/features/realtime/ProbabilityBars";
import { RiskEvolutionTimeline } from "@/features/realtime/RiskEvolutionTimeline";
import { useV3Stream } from "@/hooks/useV3Stream";

export function LiveIntelligencePage() {
  const { latest, timeline, events, connected } = useV3Stream();

  return (
    <PageContainer>
      <PageHeader
        title="Live Intelligence"
        subtitle="V3 Continuous Intelligence Engine · live global wildfire risk"
        actions={
          <Badge tone={connected ? "success" : "muted"}>
            {connected ? "● stream live" : "stream offline"}
          </Badge>
        }
      />

      <div className="space-y-4">
        <LiveIntelligenceHeader frame={latest} connected={connected} />

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <div className="space-y-4 lg:col-span-2">
            <LiveRiskMap frame={latest} connected={connected} />
            <RiskEvolutionTimeline points={timeline} live={connected} />
          </div>
          <div className="space-y-4 lg:col-span-1">
            <ProbabilityBars posterior={latest?.posterior ?? {}} />
            <EventFeed events={events} />
          </div>
        </div>
      </div>
    </PageContainer>
  );
}
