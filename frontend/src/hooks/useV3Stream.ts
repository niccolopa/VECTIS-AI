// useV3Stream — subscribe to the V3 Continuous Intelligence Engine over SSE.
//
// Connects to GET /api/v1/stream/v3/live (EventSource, which reconnects natively),
// parses each forecast frame, and exposes:
//   - `latest`    : the most recent frame (Kalman state, posterior, risk, driver)
//   - `timeline`  : risk + confidence points accumulated over time (for the chart)
//   - `events`    : a rolling, capped log of the raw events driving the changes
//   - `connected` : stream status for a live/offline indicator
//
// PERFORMANCE — the whole point of this hook. A fast pipeline can push many frames a
// second; calling setState per frame would thrash React. So incoming frames land in
// refs (no render) and a single requestAnimationFrame coalesces them into ONE state
// commit per paint (~60fps ceiling). Ten frames between two paints collapse into one
// render of the freshest state — the browser animates smoothly instead of freezing.

import { useEffect, useRef, useState } from "react";

import { liveStreamUrl } from "@/services/v3";
import type { V3Event, V3Frame, V3TimelinePoint } from "@/types/v3";

const MAX_POINTS = 240; // ~one screen of timeline history
const MAX_EVENTS = 100; // cap the rolling event log (also what the feed renders)

export interface V3Stream {
  latest: V3Frame | null;
  timeline: V3TimelinePoint[];
  events: V3Event[];
  connected: boolean;
}

const EMPTY: Omit<V3Stream, "connected"> = { latest: null, timeline: [], events: [] };

export function useV3Stream(interval?: number): V3Stream {
  const [snapshot, setSnapshot] = useState(EMPTY);
  const [connected, setConnected] = useState(false);

  // Buffers mutated on every frame without triggering a render; flushed on rAF.
  const latest = useRef<V3Frame | null>(null);
  const timeline = useRef<V3TimelinePoint[]>([]);
  const events = useRef<V3Event[]>([]);
  const raf = useRef<number | null>(null);

  useEffect(() => {
    const flush = () => {
      raf.current = null;
      setSnapshot({
        latest: latest.current,
        timeline: timeline.current,
        events: events.current,
      });
    };
    const schedule = () => {
      if (raf.current == null) raf.current = requestAnimationFrame(flush);
    };

    const source = new EventSource(liveStreamUrl(interval));
    source.onopen = () => setConnected(true);
    source.onerror = () => setConnected(false); // EventSource auto-reconnects
    source.onmessage = (ev) => {
      let frame: V3Frame;
      try {
        frame = JSON.parse(ev.data as string) as V3Frame;
      } catch {
        return; // ignore malformed frames
      }
      latest.current = frame;
      timeline.current = [
        ...timeline.current,
        { t: frame.ts, risk: frame.risk, confidence: frame.confidence, band: frame.band },
      ].slice(-MAX_POINTS);
      // Newest batch on top; keep the log bounded.
      events.current = [...frame.events, ...events.current].slice(0, MAX_EVENTS);
      schedule();
    };

    return () => {
      source.close();
      if (raf.current != null) cancelAnimationFrame(raf.current);
      raf.current = null;
    };
  }, [interval]);

  return { ...snapshot, connected };
}
