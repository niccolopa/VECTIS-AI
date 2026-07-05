// Session 37 — the terminal's end-to-end guarantees, MSW-mocked:
//   1. the map only ever requests tiles for the visible viewport (bbox + zoom);
//   2. the global ticker caps its DOM and rolls newest-first;
//   3. the drill-down brief presents a screening-only (T0) cell honestly —
//      warning notice + flat bars — and a fully-analyzed (T1/T2) cell with the
//      real distributions, posterior, and board report;
//   4. watchlist pin/unpin persists to storage and a row click re-centers.
import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import { ConnectorBadges, SyntheticDemoBanner } from "@/features/terminal/ConnectorStatusStrip";
import { GlobalEventTicker } from "@/features/terminal/GlobalEventTicker";
import { RegionBriefPanel } from "@/features/terminal/RegionBriefPanel";
import { WatchlistPanel } from "@/features/terminal/WatchlistPanel";
import { TerminalPage } from "@/pages/TerminalPage";
import { safeStorage } from "@/stores/selectionStore";
import { useWatchlistStore, type WatchlistEntry } from "@/stores/watchlistStore";
import { STUB_BOUNDS } from "@/test/maplibreStub";
import { server } from "@/test/server";
import { renderWithProviders } from "@/test/utils";
import type { CellBrief } from "@/types/cells";
import type { V3Event } from "@/types/v3";

const CELL = "85283473fffffff";

function makeEvent(i: number): V3Event {
  return {
    event_id: `evt-${i}`,
    source: i % 2 ? "usgs_quake" : "gdacs",
    variable: `var_${i}`,
    value: i,
    observed_at: new Date(2026, 6, 2, 0, 0, i % 60).toISOString(),
  };
}

const T0_BRIEF: CellBrief = {
  cell_id: CELL,
  lat: 37.3,
  lon: -121.9,
  tier: "T0",
  state: {
    cell_id: CELL,
    temperature: 40,
    humidity: 12,
    drought_index: null,
    fire_risk: null,
    precipitation_mm: null,
    earthquake_magnitude: null,
    flood_alert_level: null,
    cyclone_alert_level: null,
    extra: {},
    version: 3,
    last_updated: "2026-07-02T12:00:00Z",
    sources: ["weather_api"],
  },
  screening: { wildfire: 62.4 },
  source_cells: 1,
  analysis: null,
};

const T2_BRIEF: CellBrief = {
  ...T0_BRIEF,
  tier: "T2",
  analysis: {
    risk: 68,
    band: "high",
    confidence: 0.82,
    posterior: { baseline: 0.2, hotter_drier: 0.7, extreme_wind: 0.1 },
    scenarios: [
      {
        id: "hotter_drier",
        probability: 0.7,
        expected_band: "high",
        risk: {
          variable: "risk_score", mean: 68, std: 9, p05: 51, p50: 68, p95: 84,
          exceedance: { high: 0.8 },
        },
      },
    ],
    drivers: [
      {
        factor: "temp_anomaly_c", contribution: 1.65, direction: "increases",
        input_value: 18, baseline_value: 15, caveat: "Illustrative, uncalibrated coefficients.",
      },
      {
        factor: "wind_speed_kmh", contribution: -0.4, direction: "decreases",
        input_value: 10, baseline_value: 30, caveat: "Illustrative, uncalibrated coefficients.",
      },
    ],
    report: {
      report_id: "RPT-1",
      classification: "OPERATIONAL",
      region: "california",
      generated_at: "2026-07-02T12:00:00Z",
      bottom_line: "Sustained heat is compounding fire potential.",
      source: {
        region: "california", risk_score: 68, confidence: 0.82, risk_band: "high",
        primary_driver: "Heat & drought", scenarios: [],
      },
      analyst: {
        summary: "Risk is elevated and rising.", risk_score: 68,
        confidence_pct: 82, risk_band: "high", primary_driver: "Heat & drought",
      },
      scenarios: [
        { scenario_id: "hotter_drier", name: "hotter drier", probability_pct: 70, storyline: "Heat persists." },
      ],
      debate: { optimist_case: "Winds stay calm.", pessimist_case: "Dry lightning." },
      red_team: { challenge: "Model is uncalibrated.", blind_spots: ["arson"], residual_uncertainty_pct: 30 },
    },
  },
};

beforeEach(() => {
  useWatchlistStore.persist.clearStorage();
  useWatchlistStore.setState({ entries: [] });
});

describe("viewport-scoped tile fetching", () => {
  it("requests tiles for exactly the map's visible bbox + zoom, nothing wider", async () => {
    const requested: URL[] = [];
    server.use(
      http.get("/api/v1/tiles", ({ request }) => {
        requested.push(new URL(request.url));
        return HttpResponse.json({ zoom: 8, resolution: 5, cells: [] });
      }),
    );

    renderWithProviders(<TerminalPage />, { route: "/terminal" });

    await waitFor(() => expect(requested.length).toBeGreaterThan(0));
    const params = requested[0].searchParams;
    expect(Number(params.get("west"))).toBe(STUB_BOUNDS.west);
    expect(Number(params.get("south"))).toBe(STUB_BOUNDS.south);
    expect(Number(params.get("east"))).toBe(STUB_BOUNDS.east);
    expect(Number(params.get("north"))).toBe(STUB_BOUNDS.north);
    expect(Number(params.get("zoom"))).toBe(STUB_BOUNDS.zoom);
  });
});

describe("GlobalEventTicker", () => {
  it("caps the tape at max and keeps the newest entries", () => {
    const events = Array.from({ length: 80 }, (_, i) => makeEvent(i));
    renderWithProviders(<GlobalEventTicker events={events} max={20} />);

    expect(screen.getByText("var_0")).toBeInTheDocument(); // newest shown
    expect(screen.getByText("var_19")).toBeInTheDocument(); // last within the cap
    expect(screen.queryByText("var_20")).not.toBeInTheDocument(); // rolled off
    expect(screen.queryByText("var_79")).not.toBeInTheDocument();
  });

  it("shows an awaiting message when the tape is empty", () => {
    renderWithProviders(<GlobalEventTicker events={[]} />);
    expect(screen.getByText(/awaiting worldwide detections/i)).toBeInTheDocument();
  });
});

describe("RegionBriefPanel honesty", () => {
  it("presents a screening-only (T0) cell as an estimate, not a forecast", async () => {
    server.use(
      http.get(`/api/v1/cells/${CELL}/brief`, () => HttpResponse.json(T0_BRIEF)),
    );
    renderWithProviders(
      <RegionBriefPanel cellId={CELL} pinned={false} onTogglePin={() => {}} onClose={() => {}} />,
    );

    expect(await screen.findByText(/screening estimate only/i)).toBeInTheDocument();
    expect(screen.getByText("T0 · screened only")).toBeInTheDocument();
    // A point estimate gets a flat bar — never the box-and-whisker treatment.
    expect(screen.queryByText(/branch outcome distributions/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/bayesian posterior/i)).not.toBeInTheDocument();
  });

  it("presents a fully-analyzed (T2) cell with distributions, posterior, and report", async () => {
    server.use(
      http.get(`/api/v1/cells/${CELL}/brief`, () => HttpResponse.json(T2_BRIEF)),
    );
    renderWithProviders(
      <RegionBriefPanel cellId={CELL} pinned={false} onTogglePin={() => {}} onClose={() => {}} />,
    );

    expect(await screen.findByText("T2 · board report")).toBeInTheDocument();
    expect(screen.getByText(/branch outcome distributions/i)).toBeInTheDocument(); // whiskers
    expect(screen.getByText(/bayesian posterior/i)).toBeInTheDocument(); // bars
    expect(screen.getByText(/ai decision intelligence brief/i)).toBeInTheDocument();
    expect(screen.queryByText(/screening estimate only/i)).not.toBeInTheDocument();
  });
});

describe('RegionBriefPanel "Why" driver attribution', () => {
  it("shows the Why section for a T1/T2 cell, ranked and honestly caveated", async () => {
    server.use(http.get(`/api/v1/cells/${CELL}/brief`, () => HttpResponse.json(T2_BRIEF)));
    renderWithProviders(
      <RegionBriefPanel cellId={CELL} pinned={false} onTogglePin={() => {}} onClose={() => {}} />,
    );

    expect(await screen.findByText(/what is moving this cell's risk/i)).toBeInTheDocument();
    expect(screen.getByText("Temp anomaly c")).toBeInTheDocument();
    expect(screen.getByText(/increases/i)).toBeInTheDocument();
    expect(screen.getByText(/decreases/i)).toBeInTheDocument();
    expect(screen.getByText(/uncalibrated coefficients/i)).toBeInTheDocument();
  });

  it("never shows the Why section for a screening-only (T0) cell", async () => {
    server.use(http.get(`/api/v1/cells/${CELL}/brief`, () => HttpResponse.json(T0_BRIEF)));
    renderWithProviders(
      <RegionBriefPanel cellId={CELL} pinned={false} onTogglePin={() => {}} onClose={() => {}} />,
    );

    // Wait for the T0 chrome, then assert the Why heading is absent — a screening
    // estimate has no driver attribution to show.
    expect(await screen.findByText(/screening estimate only/i)).toBeInTheDocument();
    expect(screen.queryByText(/what is moving this cell's risk/i)).not.toBeInTheDocument();
  });
});

describe("live/synthetic transparency", () => {
  const ALL_SYNTHETIC = {
    connectors: [
      { source: "nasa_firms", label: "Fire", data_source: "synthetic_fallback" },
      { source: "usgs_quake", label: "Quake", data_source: "synthetic_fallback" },
      { source: "gdacs", label: "Multi-hazard", data_source: "synthetic_fallback" },
      { source: "weather_api", label: "Weather", data_source: "synthetic_fallback" },
    ],
    all_synthetic: true,
    any_live: false,
  };

  it("badges reflect each feed's actual data_source, not a hardcoded assumption", async () => {
    // Default MSW handler: Fire synthetic, the other three live.
    renderWithProviders(<ConnectorBadges />);

    const fire = await screen.findByTestId("connector-badge-nasa_firms");
    const quake = screen.getByTestId("connector-badge-usgs_quake");
    expect(fire).toHaveAttribute("data-state", "synthetic_fallback");
    expect(fire).toHaveTextContent(/synthetic/i);
    expect(quake).toHaveAttribute("data-state", "live");
    expect(quake).toHaveTextContent(/live/i);
  });

  it("shows the all-synthetic banner if and only if every feed is synthetic", async () => {
    // Default handler is mixed → banner absent.
    const mixed = renderWithProviders(<SyntheticDemoBanner />);
    await waitFor(() =>
      expect(mixed.queryByTestId("synthetic-demo-banner")).not.toBeInTheDocument(),
    );

    // All synthetic (the zero-credential fresh clone) → banner present.
    server.use(http.get("/api/v1/connectors", () => HttpResponse.json(ALL_SYNTHETIC)));
    renderWithProviders(<SyntheticDemoBanner />);
    expect(await screen.findByTestId("synthetic-demo-banner")).toHaveTextContent(
      /full synthetic demo/i,
    );
  });

  it("flags a synthetic-sourced event inline in the tape", () => {
    const events: V3Event[] = [
      { ...makeEvent(1), data_source: "synthetic_fallback" },
      { ...makeEvent(2), data_source: "live" },
    ];
    renderWithProviders(<GlobalEventTicker events={events} />);
    // Exactly one SYN marker — for the synthetic event, not the live one.
    expect(screen.getAllByTestId("ticker-synthetic")).toHaveLength(1);
  });
});

describe("watchlist", () => {
  it("pins persist to storage, a click re-centers, unpin removes", async () => {
    const user = userEvent.setup();
    const onFocus = vi.fn();
    useWatchlistStore.getState().pin({
      cellId: CELL, lat: 37.3, lon: -121.9, lastHazards: { wildfire: 62 },
    });

    renderWithProviders(<WatchlistPanel onFocus={onFocus} />);
    expect(screen.getByText(CELL)).toBeInTheDocument();

    // Persisted: the pin landed in the configured storage (localStorage in a real
    // browser; the safe in-memory fallback here) — what a reload rehydrates from.
    const readStored = async () => {
      const stored = (await safeStorage!.getItem("vectis-watchlist")) as {
        state: { entries: WatchlistEntry[] };
      } | null;
      return stored?.state.entries.map((e) => e.cellId) ?? [];
    };
    expect(await readStored()).toContain(CELL);

    await user.click(screen.getByTitle(`Re-center on ${CELL}`));
    expect(onFocus).toHaveBeenCalledWith(
      expect.objectContaining({ cellId: CELL, lat: 37.3, lon: -121.9 }),
    );

    await user.click(screen.getByLabelText(`Unpin ${CELL}`));
    expect(screen.queryByText(CELL)).not.toBeInTheDocument();
    expect(await readStored()).toHaveLength(0); // the unpin persisted too
  });
});
