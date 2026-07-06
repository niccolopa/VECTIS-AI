import { Navigate, Route, Routes } from "react-router-dom";
import { AppLayout } from "@/app/AppLayout";
import { OverviewPage } from "@/pages/OverviewPage";
import { TerminalPage } from "@/pages/TerminalPage";
import { RiskIntelligencePage } from "@/pages/RiskIntelligencePage";
import { ReportsPage } from "@/pages/ReportsPage";
import { ReportDetailPage } from "@/pages/ReportDetailPage";
import { SimulationsPage } from "@/pages/SimulationsPage";
import { DatasetsPage } from "@/pages/DatasetsPage";
import { NotFoundPage } from "@/pages/NotFoundPage";

export function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route path="/" element={<OverviewPage />} />
        <Route path="/terminal" element={<TerminalPage />} />
        <Route path="/risk" element={<RiskIntelligencePage />} />
        <Route path="/reports" element={<ReportsPage />} />
        <Route path="/reports/:id" element={<ReportDetailPage />} />
        <Route path="/simulations" element={<SimulationsPage />} />
        <Route path="/datasets" element={<DatasetsPage />} />
        <Route path="/index.html" element={<Navigate to="/" replace />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
