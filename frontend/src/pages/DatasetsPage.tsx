import { PageContainer, PageHeader } from "@/components/layout/Page";
import { Badge, Card, LoadingState } from "@/components/ui";
import { useDatasets } from "@/hooks/queries";
import { datasetsApi, type DatasetEntry } from "@/services/datasets";
import { titleCase } from "@/utils/format";

export function DatasetsPage() {
  const { data: datasets, isLoading } = useDatasets();

  return (
    <PageContainer>
      <PageHeader title="Datasets" subtitle="Data sources that feed the climate-risk pipeline." />

      {datasetsApi.isMock && (
        <div className="mb-4 rounded-lg border border-risk-high/40 bg-risk-high/10 px-3 py-2 text-xs text-risk-high">
          ⚠ Static catalog — there is no backend <span className="font-mono">/datasets</span> endpoint
          yet. This describes the connectors that exist in the backend (see Session 5).
        </div>
      )}

      {isLoading ? (
        <LoadingState />
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {(datasets ?? []).map((d: DatasetEntry) => (
            <Card key={d.key}>
              <div className="flex items-start justify-between">
                <div>
                  <div className="eyebrow">{titleCase(d.category)}</div>
                  <h3 className="mt-0.5 text-sm font-semibold">{d.name}</h3>
                </div>
                <Badge tone={d.status === "active" ? "success" : "muted"}>{d.status}</Badge>
              </div>
              <p className="mt-2 text-xs text-muted">{d.description}</p>
              <div className="mt-3 flex items-center justify-between text-2xs text-muted-2">
                <span>{d.provider}</span>
                {d.docsUrl && (
                  <a href={d.docsUrl} target="_blank" rel="noreferrer" className="text-accent hover:underline">
                    docs ↗
                  </a>
                )}
              </div>
            </Card>
          ))}
        </div>
      )}
    </PageContainer>
  );
}
