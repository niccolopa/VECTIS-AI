import { Link } from "react-router-dom";
import { PageContainer } from "@/components/layout/Page";
import { Button } from "@/components/ui";

export function NotFoundPage() {
  return (
    <PageContainer>
      <div className="flex h-full min-h-[300px] flex-col items-center justify-center gap-3 text-center">
        <div className="text-4xl font-bold text-muted-2">404</div>
        <p className="text-sm text-muted">This view does not exist.</p>
        <Link to="/">
          <Button variant="primary">Back to Overview</Button>
        </Link>
      </div>
    </PageContainer>
  );
}
