import { describe, expect, it } from "vitest";
import { NAV_ITEMS } from "@/components/layout/nav";

// Honesty guard (Session 40, Step 0): the V1 California demo must stay fenced
// off from the global platform so a new user can never mistake it for the
// planet-scale system. If someone drops the section marker or renames these
// back to generic "Risk Intelligence"/"Reports", this fails loudly.
describe("sidebar nav — V1/V4 separation", () => {
  const legacy = NAV_ITEMS.filter((i) => i.to === "/risk" || i.to === "/reports");

  it("marks the V1 surfaces under a Legacy Demo section", () => {
    const risk = NAV_ITEMS.find((i) => i.to === "/risk");
    expect(risk?.section).toBe("V1 Legacy Demo");
  });

  it("labels the V1 surfaces as the California case study, not generic", () => {
    for (const item of legacy) {
      expect(item.label.toLowerCase()).toMatch(/california|case study/);
    }
    expect(legacy).toHaveLength(2);
  });
});
