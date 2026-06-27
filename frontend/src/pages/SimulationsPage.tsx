import { PageContainer, PageHeader } from "@/components/layout/Page";
import { EmptyState, LoadingState } from "@/components/ui";
import { ScenarioPanel } from "@/features/simulations/ScenarioPanel";
import { useAnalyses, useAnalysis } from "@/hooks/queries";
import { useSelectionStore } from "@/stores/selectionStore";

export function SimulationsPage() {
  const { analysisId } = useSelectionStore();
  const { data: list, isLoading: listLoading } = useAnalyses();
  const effectiveId = analysisId ?? list?.[0]?.id ?? null;
  const { data: report, isLoading } = useAnalysis(effectiveId);

  return (
    <PageContainer>
      <PageHeader
        title="Simulations"
        subtitle="What-if scenarios from the Simulation agent, plus a custom scenario builder."
      />
      {isLoading || listLoading ? (
        <LoadingState />
      ) : report ? (
        <ScenarioPanel report={report} />
      ) : (
        <EmptyState
          title="No analysis to simulate"
          message="Run an analysis first — scenarios are computed as part of each analysis."
        />
      )}
    </PageContainer>
  );
}
