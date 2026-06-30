import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import { OverviewPage } from "@/pages/OverviewPage";
import { renderWithProviders } from "@/test/utils";

// Page-render + API-mocking test: OverviewPage fetches /api/v1/analyses and
// /health (mocked by MSW) and renders the recent-analyses table.
describe("OverviewPage", () => {
  it("renders recent analyses fetched from the API", async () => {
    renderWithProviders(<OverviewPage />);
    expect(screen.getByText("Operational Overview")).toBeInTheDocument();
    // From the MSW summary fixture (rendered in both the table row and the
    // "Highest risk" stat card, so there is legitimately more than one).
    expect((await screen.findAllByText("Global View")).length).toBeGreaterThan(0);
    expect(screen.getByText("approved")).toBeInTheDocument();
  });
});
