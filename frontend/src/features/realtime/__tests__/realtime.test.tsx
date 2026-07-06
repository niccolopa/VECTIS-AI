import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";

import { ProbabilityBars } from "@/features/realtime/ProbabilityBars";
import { renderWithProviders } from "@/test/utils";

// ProbabilityBars is the surviving piece of the retired V3 Live Intelligence
// console — the Global Terminal's RegionBriefPanel renders it for the Bayesian
// posterior of a promoted (T1/T2) cell.
describe("ProbabilityBars", () => {
  it("lists each scenario with its posterior", () => {
    renderWithProviders(
      <ProbabilityBars posterior={{ baseline: 0.2, hotter_drier: 0.7, extreme_wind: 0.1 }} />,
    );
    expect(screen.getByText("Hotter / Drier")).toBeInTheDocument();
    expect(screen.getByText("70%")).toBeInTheDocument();
  });
});
