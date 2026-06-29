// useTwinStream — live twin updates over the Session-9 WebSocket.
//
// Connects to WS /api/v1/stream/ws, parses each StateChange broadcast, and exposes:
//   - `latest`    : the most recent StateChange (or null)
//   - `timeline`  : RiskState points accumulated over time → feeds the Probability
//                   Timeline chart directly (seed it with the twin's current state)
//   - `connected` : socket status, for a live/offline indicator
//
// The UI updates itself as observations arrive — no refetch, no polling. Reconnects
// with a fixed backoff. ponytail: fixed 3s backoff + capped buffer; swap for
// exponential backoff only if flapping shows up in practice.

import { useEffect, useState } from "react";

import { streamSocketUrl } from "@/services/dashboard";
import type { RiskState, StateChange, TimelinePoint } from "@/types/v2";

const MAX_POINTS = 200; // cap the in-memory timeline buffer
const RECONNECT_MS = 3000;

function toPoint(risk: RiskState): TimelinePoint {
  return { t: risk.updated_at, risk: risk.risk, confidence: risk.confidence, band: risk.band };
}

export interface TwinStream {
  latest: StateChange | null;
  timeline: TimelinePoint[];
  connected: boolean;
}

export function useTwinStream(twinId: string, seed?: RiskState): TwinStream {
  const [latest, setLatest] = useState<StateChange | null>(null);
  const [connected, setConnected] = useState(false);
  const [timeline, setTimeline] = useState<TimelinePoint[]>(seed ? [toPoint(seed)] : []);

  useEffect(() => {
    // Reset the timeline when switching twins or when a seed first arrives.
    setTimeline(seed ? [toPoint(seed)] : []);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [twinId, seed?.updated_at]);

  useEffect(() => {
    let socket: WebSocket | null = null;
    let retry: ReturnType<typeof setTimeout> | null = null;
    let closed = false;

    const connect = () => {
      socket = new WebSocket(streamSocketUrl());
      socket.onopen = () => setConnected(true);
      socket.onclose = () => {
        setConnected(false);
        if (!closed) retry = setTimeout(connect, RECONNECT_MS);
      };
      socket.onerror = () => socket?.close();
      socket.onmessage = (ev) => {
        let change: StateChange;
        try {
          change = JSON.parse(ev.data as string) as StateChange;
        } catch {
          return; // ignore malformed frames
        }
        if (change.type !== "state_changed") return;
        if (change.risk.region !== twinId) return; // only this twin's updates
        setLatest(change);
        setTimeline((prev) => [...prev, toPoint(change.risk)].slice(-MAX_POINTS));
      };
    };

    connect();
    return () => {
      closed = true;
      if (retry) clearTimeout(retry);
      socket?.close();
    };
  }, [twinId]);

  return { latest, timeline, connected };
}
