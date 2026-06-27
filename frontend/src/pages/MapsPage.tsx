import { PageContainer, PageHeader } from "@/components/layout/Page";
import { Card, EmptyState, LoadingState } from "@/components/ui";
import { RiskMap } from "@/components/map/RiskMap";
import { RiskLegend } from "@/components/map/RiskLegend";
import { useAnalyses, useAnalysis, useRegions } from "@/hooks/queries";
import { useSelectionStore } from "@/stores/selectionStore";

// Full-bleed operational map of the active (or most recent) analysis.
export function MapsPage() {
  const { analysisId, selectedCellId, setCell } = useSelectionStore();
  const { data: list, isLoading: listLoading } = useAnalyses();
  const effectiveId = analysisId ?? list?.[0]?.id ?? null;
  const { data: report, isLoading } = useAnalysis(effectiveId);
  const { data: regions = [] } = useRegions();
  const region = regions.find((r) => r.key === report?.region) ?? regions[0] ?? null;

  return (
    <PageContainer full>
      <PageHeader
        title="Maps"
        subtitle={report ? `${report.area_label} · ${report.cell_risks.length} cells` : "Geographic risk view"}
      />
      <Card flush className="relative min-h-0 flex-1">
        {isLoading || listLoading ? (
          <LoadingState />
        ) : report && region ? (
          <>
            <RiskMap
              region={region}
              cells={report.cell_risks}
              selectedCellId={selectedCellId}
              onSelectCell={setCell}
            />
            <div className="absolute bottom-3 left-3">
              <RiskLegend />
            </div>
          </>
        ) : (
          <EmptyState
            title="No analysis to map"
            message="Run an analysis from Risk Intelligence to populate the map."
          />
        )}
      </Card>
    </PageContainer>
  );
}
