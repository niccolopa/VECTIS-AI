import { Link } from "react-router-dom";
import { PageContainer, PageHeader } from "@/components/layout/Page";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  EmptyState,
  ErrorState,
  LoadingState,
  RiskBadge,
  StatCard,
  Table,
  type Column,
} from "@/components/ui";
import { GlobeWidget } from "@/components/three/GlobeWidget";
import { useAnalyses, useHealth } from "@/hooks/queries";
import { relativeTime } from "@/utils/format";
import { riskColor } from "@/utils/risk";
import type { AnalysisSummary } from "@/types/api";

export function OverviewPage() {
  const { data: analyses, isLoading, isError, refetch } = useAnalyses();
  const { data: health } = useHealth();

  const count = analyses?.length ?? 0;
  const avg = count ? analyses!.reduce((s, a) => s + a.risk_score, 0) / count : 0;
  const highest = count ? analyses!.reduce((m, a) => (a.risk_score > m.risk_score ? a : m)) : null;

  const columns: Column<AnalysisSummary>[] = [
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
    {
      key: "critic",
      header: "Critic",
      render: (r) => (
        <Badge tone={r.approved ? "success" : "warning"}>{r.approved ? "approved" : "review"}</Badge>
      ),
    },
    { key: "when", header: "When", align: "right", render: (r) => <span className="text-muted">{relativeTime(r.generated_at)}</span> },
  ];

  return (
    <PageContainer>
      <PageHeader
        title="Operational Overview"
        subtitle="Current risk posture, recent analyses, and system status."
        actions={
          <Link to="/risk">
            <Button variant="primary">Run analysis</Button>
          </Link>
        }
      />

      <div className="mb-4 grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard label="Analyses (recent)" value={count} />
        <StatCard label="Avg risk score" value={avg.toFixed(0)} accent={riskColor(avg)} sub="/100" />
        <StatCard
          label="Highest risk"
          value={highest ? highest.risk_score.toFixed(0) : "—"}
          accent={highest ? riskColor(highest.risk_score) : undefined}
          sub={highest?.area_label}
        />
        <StatCard
          label="System"
          value={health ? "Online" : "—"}
          accent="#22c55e"
          sub={health ? `v${health.version} · ${health.env}` : undefined}
        />
      </div>

      <Card flush className="mb-4">
        <div className="p-4">
          <CardHeader
            title="Global Tactical View"
            eyebrow="Geospatial intelligence"
            actions={<span className="text-2xs text-muted-2">drag to orbit · scroll to zoom</span>}
          />
        </div>
        <div className="h-72 w-full">
          <GlobeWidget />
        </div>
      </Card>

      <Card flush>
        <div className="p-4">
          <CardHeader title="Recent Analyses" eyebrow="Decision reports" />
        </div>
        {isLoading ? (
          <LoadingState />
        ) : isError ? (
          <ErrorState message="Could not load analyses." onRetry={() => refetch()} />
        ) : (
          <Table
            columns={columns}
            rows={analyses ?? []}
            rowKey={(r) => r.id}
            empty={
              <EmptyState
                title="No analyses yet"
                message="Run your first climate risk analysis to populate the console."
                action={
                  <Link to="/risk">
                    <Button variant="primary">Go to Risk Intelligence</Button>
                  </Link>
                }
              />
            }
          />
        )}
      </Card>
    </PageContainer>
  );
}
