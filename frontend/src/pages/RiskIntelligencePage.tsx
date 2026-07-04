import { PageContainer, PageHeader } from "@/components/layout/Page";
import { LegacyDemoBanner } from "@/components/LegacyDemoBanner";
import { Button, Card, EmptyState, ErrorState, LoadingState } from "@/components/ui";
import { RiskMap } from "@/components/map/RiskMap";
import { WORLD, WORLD_ZOOM } from "@/components/map/world";
import { RegionSelector } from "@/features/risk/RegionSelector";
import { RiskDetailPanel } from "@/features/risk/RiskDetailPanel";
import { useAnalysis, useRunAnalysis } from "@/hooks/queries";
import { useSelectionStore } from "@/stores/selectionStore";

export function RiskIntelligencePage() {
  const { regionKey, analysisId, setRegion } = useSelectionStore();
  const run = useRunAnalysis();
  const { data: report, isLoading, isError, refetch } = useAnalysis(analysisId);

  return (
    <PageContainer full>
      <PageHeader
        title="California Case Study — V1 Legacy Demo"
        subtitle="The original reactive pipeline: California-trained wildfire model with SHAP-attributed drivers."
        actions={
          <>
            <RegionSelector value={regionKey} onChange={setRegion} />
            <Button
              variant="primary"
              loading={run.isPending}
              onClick={() => run.mutate({ region: regionKey })}
            >
              Run analysis
            </Button>
          </>
        }
      />

      <LegacyDemoBanner />

      {run.isError && (
        <div className="mb-3 rounded-lg border border-risk-severe/40 bg-risk-severe/10 px-3 py-2 text-xs text-risk-severe">
          {(run.error as Error).message}
        </div>
      )}

      <div className="grid min-h-0 flex-1 grid-cols-1 gap-4 lg:grid-cols-3">
        <Card flush className="relative min-h-[420px] lg:col-span-2">
          <RiskMap region={WORLD} cells={[]} zoom={WORLD_ZOOM} />
          <div className="pointer-events-none absolute left-3 top-3 rounded-full border border-border-strong bg-bg/70 px-3 py-1 text-2xs uppercase tracking-wide text-muted backdrop-blur">
            Global view · select a region and run an analysis
          </div>
        </Card>

        <Card flush className="min-h-[420px] overflow-hidden">
          {isLoading ? (
            <LoadingState />
          ) : isError ? (
            <ErrorState message="Could not load the analysis." onRetry={() => refetch()} />
          ) : report ? (
            <RiskDetailPanel report={report} />
          ) : (
            <EmptyState
              title="No analysis selected"
              message="Pick a region and run an analysis to see the risk score, drivers, and recommended actions."
            />
          )}
        </Card>
      </div>
    </PageContainer>
  );
}
