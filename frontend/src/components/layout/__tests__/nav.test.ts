import { describe, expect, it } from "vitest";
import { NAV_ITEMS } from "@/components/layout/nav";

// Honesty guard (Session 40, tightened in Session 42): the archived V1
// California demo must stay fenced off — and now *secondary* — so a new user
// can never mistake it for the planet-scale system. If someone drops the
// section marker, renames the surfaces back to generic labels, or reorders
// them above the global platform, this fails loudly.
describe("sidebar nav — V1 origin-demo separation", () => {
  const archiveStart = NAV_ITEMS.findIndex((i) => i.section);
  const legacy = NAV_ITEMS.filter((i) => i.to === "/risk" || i.to === "/reports");

  it("marks the V1 surfaces under a secondary Origin Demo archive section", () => {
    const risk = NAV_ITEMS.find((i) => i.to === "/risk");
    expect(risk?.section).toMatch(/origin demo/i);
    expect(risk?.section).toMatch(/archive/i);
  });

  it("keeps the archive group last — below every primary platform item", () => {
    expect(archiveStart).toBeGreaterThan(0);
    const archived = NAV_ITEMS.slice(archiveStart).map((i) => i.to);
    expect(archived.sort()).toEqual(["/reports", "/risk"].sort());
  });

  it("labels the V1 surfaces as the California case study, not generic", () => {
    for (const item of legacy) {
      expect(item.label.toLowerCase()).toMatch(/california|case study/);
    }
    expect(legacy).toHaveLength(2);
  });
});
