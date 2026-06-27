import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import { ReportViewer } from "@/features/reports/ReportViewer";
import { renderWithProviders } from "@/test/utils";
import { reportFixture } from "@/test/fixtures";

describe("ReportViewer", () => {
  it("separates AI insight, supporting evidence, and human decision", () => {
    renderWithProviders(<ReportViewer report={reportFixture} />);
    // Band headers are prefixed with a "● " bullet, so match by substring.
    expect(screen.getByText(/AI-Generated Insight/)).toBeInTheDocument();
    expect(screen.getByText(/Supporting Evidence/)).toBeInTheDocument();
    expect(screen.getByText(/Human Decision/)).toBeInTheDocument();
  });

  it("shows the summary, an evidence statement, and the Critic verdict", () => {
    renderWithProviders(<ReportViewer report={reportFixture} />);
    expect(screen.getByText(reportFixture.summary)).toBeInTheDocument();
    expect(screen.getByText(/Drought conditions increases risk/)).toBeInTheDocument();
    expect(screen.getByText(/Approved/)).toBeInTheDocument();
  });
});
