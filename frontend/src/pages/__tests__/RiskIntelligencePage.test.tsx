import { beforeEach, describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RiskIntelligencePage } from "@/pages/RiskIntelligencePage";
import { useSelectionStore } from "@/stores/selectionStore";
import { renderWithProviders } from "@/test/utils";

describe("RiskIntelligencePage", () => {
  beforeEach(() => {
    // Reset the shared selection store between tests.
    useSelectionStore.setState({ regionKey: "liguria", analysisId: null, selectedCellId: null });
  });

  it("runs an analysis and shows the risk detail (API-mocked end to end)", async () => {
    renderWithProviders(<RiskIntelligencePage />);

    // Prompt before any analysis exists.
    expect(screen.getByText(/Run an analysis to render/)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Run analysis" }));

    // After the mocked POST + GET, the detail panel renders the report.
    expect(await screen.findByText(/AI Summary/)).toBeInTheDocument();
    expect(screen.getAllByText("Liguria, Italy").length).toBeGreaterThan(0);
    // Severe risk band from the fixture (shown in the risk badge and the
    // detail panel, so there is legitimately more than one).
    expect(screen.getAllByText("Severe").length).toBeGreaterThan(0);
  });
});
