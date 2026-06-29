import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";

import { EventFeed } from "@/features/realtime/EventFeed";
import { LiveIntelligenceHeader } from "@/features/realtime/LiveIntelligenceHeader";
import { LiveRiskMap } from "@/features/realtime/LiveRiskMap";
import { ProbabilityBars } from "@/features/realtime/ProbabilityBars";
import { RiskEvolutionTimeline } from "@/features/realtime/RiskEvolutionTimeline";
import { renderWithProviders } from "@/test/utils";
import type { V3Event, V3Frame, V3TimelinePoint } from "@/types/v3";

function makeEvent(i: number): V3Event {
  return {
    event_id: `evt-${i}`,
    source: i % 2 ? "nasa_firms" : "weather_api",
    variable: `var_${i}`,
    value: i,
    observed_at: new Date(2026, 0, 1, 0, 0, i % 60).toISOString(),
  };
}

function makeFrame(tick: number): V3Frame {
  return {
    tick,
    cell: "Liguria_01",
    cell_id: "44.4,8.9",
    ts: new Date(2026, 0, 1, 0, 0, tick).toISOString(),
    risk: 70 + tick,
    prev_risk: tick === 0 ? null : 69 + tick,
    band: "severe",
    confidence: 0.8,
    driver: "Temperature & rainfall anomaly",
    temp_mean: 30 + tick,
    temp_variance: 1.5,
    temp_delta: 1.0,
    posterior: { baseline: 0.2, hotter_drier: 0.7, extreme_wind: 0.1 },
    events: [makeEvent(tick)],
    report_id: null,
    report: null,
  };
}

describe("EventFeed", () => {
  it("renders newest events but never more than the max limit", () => {
    // 80 events newest-first; the feed must cap the DOM at `max`.
    const events = Array.from({ length: 80 }, (_, i) => makeEvent(i));
    renderWithProviders(<EventFeed events={events} max={20} />);

    expect(screen.getByText("var_0")).toBeInTheDocument(); // newest shown
    expect(screen.getByText("var_19")).toBeInTheDocument(); // last within the cap
    expect(screen.queryByText("var_20")).not.toBeInTheDocument(); // beyond the cap, dropped
    expect(screen.queryByText("var_79")).not.toBeInTheDocument();
  });

  it("shows an awaiting message when empty", () => {
    renderWithProviders(<EventFeed events={[]} />);
    expect(screen.getByText(/Awaiting the live stream/)).toBeInTheDocument();
  });
});

describe("real-time components render with continuous mock data", () => {
  const frame = makeFrame(5);
  const timeline: V3TimelinePoint[] = Array.from({ length: 30 }, (_, i) => ({
    t: new Date(2026, 0, 1, 0, 0, i).toISOString(),
    risk: 60 + i,
    confidence: 0.5 + i / 100,
    band: "severe",
  }));

  it("LiveIntelligenceHeader shows the cell, risk, driver and confidence", () => {
    renderWithProviders(<LiveIntelligenceHeader frame={frame} connected />);
    expect(screen.getByText("Liguria_01")).toBeInTheDocument();
    expect(screen.getByText(/Temperature & rainfall anomaly/)).toBeInTheDocument();
    expect(screen.getByText("● live")).toBeInTheDocument();
  });

  it("LiveIntelligenceHeader renders placeholders before the first frame", () => {
    renderWithProviders(<LiveIntelligenceHeader frame={null} connected={false} />);
    expect(screen.getByText("offline")).toBeInTheDocument();
  });

  it("ProbabilityBars lists each scenario with its posterior", () => {
    renderWithProviders(<ProbabilityBars posterior={frame.posterior} />);
    expect(screen.getByText("Hotter / Drier")).toBeInTheDocument();
    expect(screen.getByText("70%")).toBeInTheDocument();
  });

  it("RiskEvolutionTimeline renders an accumulating series", () => {
    const { container } = renderWithProviders(
      <RiskEvolutionTimeline points={timeline} live />,
    );
    expect(screen.getByText("Risk & confidence over time")).toBeInTheDocument();
    expect(container.querySelector(".recharts-responsive-container")).toBeTruthy();
  });

  it("LiveRiskMap renders the map card without crashing", () => {
    renderWithProviders(<LiveRiskMap frame={frame} connected />);
    expect(screen.getByText(/Live · 75\/100/)).toBeInTheDocument();
  });
});
