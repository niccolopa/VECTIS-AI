import { PageContainer, PageHeader } from "@/components/layout/Page";
import { Card } from "@/components/ui";
import { RiskMap } from "@/components/map/RiskMap";
import { WORLD, WORLD_ZOOM } from "@/components/map/world";

// Global operational basemap — the whole theatre of operations. Detailed,
// cell-level risk is plotted live in the Live Intelligence console; this view
// frames the planet rather than any single region.
export function MapsPage() {
  return (
    <PageContainer full>
      <PageHeader title="Maps" subtitle="Global operational view" />
      <Card flush className="relative min-h-0 flex-1">
        <RiskMap region={WORLD} cells={[]} zoom={WORLD_ZOOM} />
        <div className="pointer-events-none absolute left-3 top-3 rounded-full border border-border-strong bg-bg/70 px-3 py-1 text-2xs uppercase tracking-wide text-muted backdrop-blur">
          Global theatre · live hotspots in Live Intelligence
        </div>
      </Card>
    </PageContainer>
  );
}
