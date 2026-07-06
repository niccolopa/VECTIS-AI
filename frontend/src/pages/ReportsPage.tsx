import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { PageContainer, PageHeader } from "@/components/layout/Page";
import { LegacyDemoBanner } from "@/components/LegacyDemoBanner";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  LoadingState,
  Modal,
  RiskBadge,
  Table,
  type Column,
} from "@/components/ui";
import { useAnalyses, useDeleteAnalysis } from "@/hooks/queries";
import { dateTime } from "@/utils/format";
import { riskColor } from "@/utils/risk";
import type { AnalysisSummary } from "@/types/api";

export function ReportsPage() {
  const navigate = useNavigate();
  const { data: analyses, isLoading, isError, refetch } = useAnalyses(100);
  const remove = useDeleteAnalysis();
  // The report queued for deletion — a confirmation modal gates the actual call.
  const [pendingDelete, setPendingDelete] = useState<AnalysisSummary | null>(null);

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
    {
      key: "delete",
      header: "",
      align: "right",
      render: (r) => (
        <button
          type="button"
          aria-label={`Delete report ${r.id.slice(0, 8)}`}
          onClick={(e) => {
            e.stopPropagation(); // the row itself navigates to the report
            setPendingDelete(r);
          }}
          className="rounded border border-border-strong px-1.5 py-0.5 text-2xs text-muted hover:border-risk-severe/60 hover:text-risk-severe"
        >
          ✕
        </button>
      ),
    },
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

      <Modal
        open={pendingDelete !== null}
        onClose={() => setPendingDelete(null)}
        title="Delete report?"
      >
        <p className="text-sm text-muted">
          Permanently delete the {pendingDelete?.area_label} report{" "}
          <span className="font-mono text-xs">{pendingDelete?.id.slice(0, 8)}</span> generated{" "}
          {pendingDelete && dateTime(pendingDelete.generated_at)}? This cannot be undone.
        </p>
        {remove.isError && (
          <p className="mt-2 text-xs text-risk-severe">{(remove.error as Error).message}</p>
        )}
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="ghost" onClick={() => setPendingDelete(null)}>
            Cancel
          </Button>
          <Button
            variant="danger"
            loading={remove.isPending}
            onClick={() =>
              pendingDelete &&
              remove.mutate(pendingDelete.id, { onSuccess: () => setPendingDelete(null) })
            }
          >
            Delete
          </Button>
        </div>
      </Modal>
    </PageContainer>
  );
}
