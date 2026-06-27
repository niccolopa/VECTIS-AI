import { PageContainer, PageHeader } from "@/components/layout/Page";
import { Button, Card, EmptyState, ErrorState, LoadingState } from "@/components/ui";
import { RiskMap } from "@/components/map/RiskMap";
import { RiskLegend } from "@/components/map/RiskLegend";
import { RegionSelector } from "@/features/risk/RegionSelector";
import { RiskDetailPanel } from "@/features/risk/RiskDetailPanel";
import { useAnalysis, useRegions, useRunAnalysis } from "@/hooks/queries";
import { useSelectionStore } from "@/stores/selectionStore";

export function RiskIntelligencePage() {
  const { regionKey, analysisId, selectedCellId, setRegion, setCell } = useSelectionStore();
  const { data: regions = [] } = useRegions();
  const run = useRunAnalysis();
  const { data: report, isLoading, isError, refetch } = useAnalysis(analysisId);

  const mapRegion =
    regions.find((r) => r.key === (report?.region ?? regionKey)) ?? regions[0] ?? null;
  const selectedCell = report?.cell_risks.find((c) => c.cell_id === selectedCellId) ?? null;

  return (
    <PageContainer full>
      <PageHeader
        title="Climate Risk Intelligence"
        subtitle="Wildfire risk by geographic cell, with model-attributed drivers."
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

      {run.isError && (
        <div className="mb-3 rounded-lg border border-risk-severe/40 bg-risk-severe/10 px-3 py-2 text-xs text-risk-severe">
          {(run.error as Error).message}
        </div>
      )}

      <div className="grid min-h-0 flex-1 grid-cols-1 gap-4 lg:grid-cols-3">
        <Card flush className="relative min-h-[420px] lg:col-span-2">
          {mapRegion && report ? (
            <>
              <RiskMap
                region={mapRegion}
                cells={report.cell_risks}
                selectedCellId={selectedCellId}
                onSelectCell={setCell}
              />
              <div className="absolute bottom-3 left-3">
                <RiskLegend />
              </div>
            </>
          ) : (
            <div className="flex h-full items-center justify-center text-center text-sm text-muted">
              {run.isPending
                ? "Running multi-agent analysis…"
                : "Run an analysis to render the regional risk map."}
            </div>
          )}
        </Card>

        <Card flush className="min-h-[420px] overflow-hidden">
          {isLoading ? (
            <LoadingState />
          ) : isError ? (
            <ErrorState message="Could not load the analysis." onRetry={() => refetch()} />
          ) : report ? (
            <RiskDetailPanel report={report} selectedCell={selectedCell} />
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
