// usePlayback — the /terminal scrub engine (Session 39).
//
// Live mode is the default; entering replay fetches the viewport's snapshot history
// over a time window and lets the operator scrub it. The current frame's cells are
// mapped to TileCell shape so the *same* WorldRiskMap paints them — but under the
// hazard each snapshot was actually recorded on, so a flood replay respects the flood
// toggle exactly as live does. Nothing here is live: every frame is a past recording
// (illustrative coefficients), which the caller renders with unmistakable replay chrome.
import { useCallback, useEffect, useState } from "react";

import { fetchPlaybackFrames } from "@/services/history";
import type { PlaybackFrame } from "@/types/history";
import type { TileCell, Viewport } from "@/types/tiles";

/** Default look-back and resolution of the scrub timeline. */
const WINDOW_HOURS = 24;
const STEPS = 48; // ~30-min slices over 24h
const PLAY_MS = 900; // auto-advance cadence

function frameToCells(frame: PlaybackFrame | undefined): TileCell[] {
  if (!frame) return [];
  return frame.cells.map((c) => ({
    cell_id: c.cell_id,
    lat: c.lat,
    lon: c.lon,
    hazards: { [c.hazard]: c.risk }, // paint under the recorded hazard only
    source_cells: 1,
  }));
}

export interface Playback {
  active: boolean;
  loading: boolean;
  error: string | null;
  frames: PlaybackFrame[];
  index: number;
  playing: boolean;
  currentTs: string | null;
  cells: TileCell[];
  enter: () => void;
  exit: () => void;
  setIndex: (i: number) => void;
  togglePlay: () => void;
}

export function usePlayback(viewport: Viewport | null): Playback {
  const [active, setActive] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [frames, setFrames] = useState<PlaybackFrame[]>([]);
  const [index, setIndexState] = useState(0);
  const [playing, setPlaying] = useState(false);

  const enter = useCallback(() => {
    if (!viewport) return;
    setActive(true);
    setLoading(true);
    setError(null);
    setPlaying(false);
    const end = new Date();
    const start = new Date(end.getTime() - WINDOW_HOURS * 3600_000);
    fetchPlaybackFrames(viewport, {
      start: start.toISOString(),
      end: end.toISOString(),
      steps: STEPS,
    })
      .then((res) => {
        setFrames(res.frames);
        setIndexState(res.frames.length - 1); // land on the most recent slice
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "history unavailable"))
      .finally(() => setLoading(false));
  }, [viewport]);

  const exit = useCallback(() => {
    setActive(false);
    setPlaying(false);
    setFrames([]);
    setIndexState(0);
  }, []);

  const setIndex = useCallback((i: number) => {
    setPlaying(false); // a manual scrub pauses autoplay
    setIndexState(i);
  }, []);

  const togglePlay = useCallback(() => setPlaying((p) => !p), []);

  // Autoplay: advance one slice per tick, stopping at the end.
  const framesLen = frames.length;
  useEffect(() => {
    if (!playing || framesLen === 0) return;
    const id = window.setInterval(() => {
      setIndexState((i) => {
        if (i >= framesLen - 1) {
          setPlaying(false);
          return i;
        }
        return i + 1;
      });
    }, PLAY_MS);
    return () => window.clearInterval(id);
  }, [playing, framesLen]);

  const clamped = Math.min(Math.max(index, 0), Math.max(framesLen - 1, 0));
  const current = frames[clamped];

  return {
    active,
    loading,
    error,
    frames,
    index: clamped,
    playing,
    currentTs: current?.ts ?? null,
    cells: active ? frameToCells(current) : [],
    enter,
    exit,
    setIndex,
    togglePlay,
  };
}
