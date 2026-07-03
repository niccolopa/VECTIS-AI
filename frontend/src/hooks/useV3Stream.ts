// useV3Stream / useTerminalStream — subscribe to the V3 engine over SSE.
//
// Two stream contracts share one transport core:
//   - useV3Stream      : GET /api/v1/stream/v3/live — the Session-24 single-headline
//                        console frame (Kalman state, posterior, risk, driver).
//   - useTerminalStream: GET /api/v1/stream/v3/terminal — the Session-37 global
//                        terminal frame, scoped to the client's current viewport
//                        (screened cells in view + the worldwide event tape).
//
// PERFORMANCE — the whole point of the core. A fast pipeline can push many frames a
// second; calling setState per frame would thrash React. So incoming frames land in
// a ref (no render) and a single requestAnimationFrame coalesces them into ONE state
// commit per paint (~60fps ceiling). Ten frames between two paints collapse into one
// render of the freshest state — the browser animates smoothly instead of freezing.

import { useEffect, useRef, useState } from "react";

import { liveStreamUrl, terminalStreamUrl } from "@/services/v3";
import type { TileCell, Viewport } from "@/types/tiles";
import type { TerminalFrame, V3Event, V3Frame, V3TimelinePoint } from "@/types/v3";

const MAX_POINTS = 240; // ~one screen of timeline history
const MAX_EVENTS = 100; // cap the rolling event log (also what the feed renders)

/** The rAF-coalesced EventSource core: accumulate frames via `reduce` (a stable,
 * module-level function), commit at most one snapshot per paint. `url = null`
 * means "not ready to connect yet" (e.g. the map hasn't reported a viewport). */
function useCoalescedStream<S>(
  url: string | null,
  initial: S,
  reduce: (acc: S, frame: unknown) => S,
): { snapshot: S; connected: boolean } {
  const [snapshot, setSnapshot] = useState(initial);
  const [connected, setConnected] = useState(false);

  const acc = useRef<S>(initial);
  const raf = useRef<number | null>(null);
  const initialRef = useRef(initial);
  const reduceRef = useRef(reduce);
  reduceRef.current = reduce;

  useEffect(() => {
    if (url == null) return;
    // Fresh accumulator per connection (a viewport change is a new scope).
    acc.current = initialRef.current;

    const flush = () => {
      raf.current = null;
      setSnapshot(acc.current);
    };
    const schedule = () => {
      if (raf.current == null) raf.current = requestAnimationFrame(flush);
    };

    const source = new EventSource(url);
    source.onopen = () => setConnected(true);
    source.onerror = () => setConnected(false); // EventSource auto-reconnects
    source.onmessage = (ev) => {
      let frame: unknown;
      try {
        frame = JSON.parse(ev.data as string);
      } catch {
        return; // ignore malformed frames
      }
      acc.current = reduceRef.current(acc.current, frame);
      schedule();
    };

    return () => {
      source.close();
      if (raf.current != null) cancelAnimationFrame(raf.current);
      raf.current = null;
    };
  }, [url]);

  return { snapshot, connected };
}

// ── the Session-24 live-console contract (unchanged) ───────────────────────────

export interface V3Stream {
  latest: V3Frame | null;
  timeline: V3TimelinePoint[];
  events: V3Event[];
  connected: boolean;
}

type V3Acc = Omit<V3Stream, "connected">;

const V3_EMPTY: V3Acc = { latest: null, timeline: [], events: [] };

function reduceV3(acc: V3Acc, data: unknown): V3Acc {
  const frame = data as V3Frame;
  return {
    latest: frame,
    timeline: [
      ...acc.timeline,
      { t: frame.ts, risk: frame.risk, confidence: frame.confidence, band: frame.band },
    ].slice(-MAX_POINTS),
    // Newest batch on top; keep the log bounded.
    events: [...frame.events, ...acc.events].slice(0, MAX_EVENTS),
  };
}

export function useV3Stream(interval?: number): V3Stream {
  const { snapshot, connected } = useCoalescedStream(liveStreamUrl(interval), V3_EMPTY, reduceV3);
  return { ...snapshot, connected };
}

// ── the Session-37 viewport-scoped terminal contract ───────────────────────────

export interface TerminalStream {
  latest: TerminalFrame | null;
  /** The viewport's screened cells from the freshest frame (live map recolor). */
  cells: TileCell[];
  /** Worldwide rolling event tape, newest first, capped. */
  events: V3Event[];
  connected: boolean;
}

type TerminalAcc = Omit<TerminalStream, "connected">;

const TERMINAL_EMPTY: TerminalAcc = { latest: null, cells: [], events: [] };

function reduceTerminal(acc: TerminalAcc, data: unknown): TerminalAcc {
  const frame = data as TerminalFrame;
  return {
    latest: frame,
    cells: frame.cells,
    events: [...frame.events, ...acc.events].slice(0, MAX_EVENTS),
  };
}

export function useTerminalStream(viewport: Viewport | null): TerminalStream {
  const url = viewport ? terminalStreamUrl(viewport) : null;
  const { snapshot, connected } = useCoalescedStream(url, TERMINAL_EMPTY, reduceTerminal);
  return { ...snapshot, connected };
}
