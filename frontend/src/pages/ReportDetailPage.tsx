import { Link, useParams } from "react-router-dom";
import { PageContainer, PageHeader } from "@/components/layout/Page";
import { LegacyDemoBanner } from "@/components/LegacyDemoBanner";
import { Button, ErrorState, LoadingState } from "@/components/ui";
import { ReportViewer } from "@/features/reports/ReportViewer";
import { useAnalysis } from "@/hooks/queries";

export function ReportDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data: report, isLoading, isError, refetch } = useAnalysis(id);

  return (
    <PageContainer>
      <PageHeader
        title="Report"
        subtitle={id ? `Analysis ${id}` : undefined}
        actions={
          <Link to="/reports">
            <Button variant="ghost">← All reports</Button>
          </Link>
        }
      />
      <LegacyDemoBanner />
      {isLoading ? (
        <LoadingState />
      ) : isError || !report ? (
        <ErrorState title="Report not found" message="This analysis may not exist." onRetry={() => refetch()} />
      ) : (
        <ReportViewer report={report} />
      )}
    </PageContainer>
  );
}
