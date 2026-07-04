// Session 39 — playback mode on /terminal, MSW-mocked:
//   1. entering replay fetches the viewport's history and shows unambiguous replay
//      chrome (amber banner + timestamp), with the live badge gone;
//   2. scrubbing the timeline repaints the map from the historical frame at that slice;
//   3. RETURN TO LIVE exits replay and restores the live tape.
// The map is the maplibre stub (STUB_BOUNDS); we assert on the surrounding chrome and
// the frame data the page hands the map, not on GL rendering.
import { beforeEach, describe, expect, it } from "vitest";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import { TerminalPage } from "@/pages/TerminalPage";
import { STUB_BOUNDS } from "@/test/maplibreStub";
import { server } from "@/test/server";
import { renderWithProviders } from "@/test/utils";
import type { PlaybackResponse } from "@/types/history";

const CELL_A = "85283473fffffff";
const CELL_B = "85283447fffffff";

// Two slices: the early one has only cell A (flood), the late one adds cell B (quake).
function playbackFixture(): PlaybackResponse {
  return {
    start: "2026-07-03T00:00:00Z",
    end: "2026-07-04T00:00:00Z",
    frames: [
      {
        ts: "2026-07-03T12:00:00Z",
        cells: [
          { cell_id: CELL_A, lat: 37.5, lon: -120.0, risk: 44, confidence: 0.5, hazard: "flood" },
        ],
      },
      {
        ts: "2026-07-03T23:30:00Z",
        cells: [
          { cell_id: CELL_A, lat: 37.5, lon: -120.0, risk: 71, confidence: 0.7, hazard: "flood" },
          { cell_id: CELL_B, lat: 38.0, lon: -121.0, risk: 88, confidence: 0.8, hazard: "quake" },
        ],
      },
    ],
  };
}

describe("terminal playback mode", () => {
  beforeEach(() => {
    server.use(
      http.get("/api/v1/tiles", () => HttpResponse.json({ zoom: STUB_BOUNDS.zoom, resolution: 5, cells: [] })),
      http.get("/api/v1/history/frames", () => HttpResponse.json(playbackFixture())),
    );
  });

  it("enters replay with unambiguous chrome, scrubs, and returns to live", async () => {
    const user = userEvent.setup();
    renderWithProviders(<TerminalPage />, { route: "/terminal" });

    // Live to start: the replay entry point is offered, no replay chrome yet.
    const enter = await screen.findByRole("button", { name: /◀ replay/i });
    expect(screen.queryByLabelText("Replay timestamp")).not.toBeInTheDocument();

    await user.click(enter);

    // Replay chrome is now unmistakable, and lands on the most recent slice (23:30).
    await waitFor(() =>
      expect(screen.getByLabelText("Replay timestamp")).toHaveTextContent("2026-07-03 23:30 UTC"),
    );
    expect(screen.getByText(/replay mode/i)).toBeInTheDocument();
    expect(screen.queryByText(/stream live/i)).not.toBeInTheDocument();
    // Late slice paints both cells.
    expect(screen.getByText(/2 cells in view/i)).toBeInTheDocument();

    // Scrub back to the first slice → only cell A is painted.
    const scrub = screen.getByLabelText("Scrub history") as HTMLInputElement;
    expect(scrub.max).toBe("1");
    fireEvent.change(scrub, { target: { value: "0" } });
    await waitFor(() =>
      expect(screen.getByLabelText("Replay timestamp")).toHaveTextContent("2026-07-03 12:00 UTC"),
    );
    expect(screen.getByText(/1 cells in view/i)).toBeInTheDocument();

    // Return to live restores the tape and drops replay chrome.
    await user.click(screen.getByRole("button", { name: /return to live/i }));
    await waitFor(() =>
      expect(screen.queryByLabelText("Replay timestamp")).not.toBeInTheDocument(),
    );
    expect(screen.getByRole("button", { name: /◀ replay/i })).toBeInTheDocument();
  });
});
