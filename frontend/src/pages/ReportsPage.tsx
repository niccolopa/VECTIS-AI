import { useNavigate } from "react-router-dom";
import { PageContainer, PageHeader } from "@/components/layout/Page";
import { LegacyDemoBanner } from "@/components/LegacyDemoBanner";
import {
  Badge,
  Card,
  EmptyState,
  ErrorState,
  LoadingState,
  RiskBadge,
  Table,
  type Column,
} from "@/components/ui";
import { useAnalyses } from "@/hooks/queries";
import { dateTime } from "@/utils/format";
import { riskColor } from "@/utils/risk";
import type { AnalysisSummary } from "@/types/api";

export function ReportsPage() {
  const navigate = useNavigate();
  const { data: analyses, isLoading, isError, refetch } = useAnalyses(100);

  const columns: Column<AnalysisSummary>[] = [
    { key: "id", header: "ID", render: (r) => <span className="font-mono text-xs text-muted">{r.id.slice(0, 8)}</span> },
    { key: "area", header: "Area", render: (r) => <span className="font-medium">{r.area_label}</span> },
    {
      key: "risk",
      header: "Risk",
      align: "right",
      render: (r) => (
        <span className="font-semibold tabular-nums" style={{ color: riskColor(r.risk_score) }}>
          {r.risk_score.toFixed(0)}
        </span>
      ),
    },
    { key: "band", header: "Band", render: (r) => <RiskBadge band={r.risk_band} /> },
    { key: "conf", header: "Conf.", align: "right", render: (r) => <span className="tabular-nums text-muted">{Math.round(r.confidence * 100)}%</span> },
    { key: "critic", header: "Critic", render: (r) => <Badge tone={r.approved ? "success" : "warning"}>{r.approved ? "approved" : "review"}</Badge> },
    { key: "when", header: "Generated", align: "right", render: (r) => <span className="text-muted">{dateTime(r.generated_at)}</span> },
  ];

  return (
    <PageContainer>
      <PageHeader title="Case Study Reports — Origin Demo (V1 Archive)" subtitle="Every California Case Study analysis the archived V1 pipeline has produced. Select one to view the full report." />
      <LegacyDemoBanner />
      <Card flush>
        {isLoading ? (
          <LoadingState />
        ) : isError ? (
          <ErrorState message="Could not load reports." onRetry={() => refetch()} />
        ) : (
          <Table
            columns={columns}
            rows={analyses ?? []}
            rowKey={(r) => r.id}
            onRowClick={(r) => navigate(`/reports/${r.id}`)}
            empty={<EmptyState title="No reports yet" message="Run an analysis from the California Case Study page." />}
          />
        )}
      </Card>
    </PageContainer>
  );
}
