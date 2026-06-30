import { beforeEach, describe, expect, it } from "vitest";
import { waitFor } from "@testing-library/react";
import { RegionSelector } from "@/features/risk/RegionSelector";
import { useSelectionStore } from "@/stores/selectionStore";
import { renderWithProviders } from "@/test/utils";

// Failsafe: a stale/invalid persisted region (e.g. "atlantis" injected into
// localStorage) must not crash the app — useRegions repoints the store to a
// valid backend region. The mocked /api/v1/regions returns only "liguria", so
// the unknown "california" default falls through to the first available region.
describe("region failsafe", () => {
  beforeEach(() => {
    useSelectionStore.setState({ regionKey: "atlantis", analysisId: null, selectedCellId: null });
  });

  it("repoints a stale region to an available one instead of crashing", async () => {
    renderWithProviders(<RegionSelector value="atlantis" onChange={() => {}} />);
    await waitFor(() => expect(useSelectionStore.getState().regionKey).toBe("liguria"));
  });
});
