// TerminalPage — the global disaster terminal at /terminal. One dense, dark,
// multi-pane console over the real pipeline (Sessions 30–36):
//
//   ┌──────────────────────────────┬──────────────┐
//   │ WorldRiskMap (primary)       │ Watchlist    │
//   │  · tiles @ viewport bbox     │ Brief drawer │
//   │  · hazard toggles overlay    │  (when a     │
//   │  · live SSE recolor          │   cell is    │
//   │                              │   selected)  │
//   ├──────────────────────────────┴──────────────┤
//   │ GlobalEventTicker (worldwide tape)           │
//   └──────────────────────────────────────────────┘
//
// Data flow: the map reports its debounced viewport → (a) useTiles fetches the
// bbox-scoped tile snapshot, (b) useTerminalStream opens the viewport-scoped SSE
// stream. Whichever produced cells most recently paints the map, so a pan renders
// immediately from HTTP while the stream reconnects, then live frames take over.
// Routed additively — /live and /dashboard are untouched; Overview stays the
// landing route (the terminal is a deliberate destination, not a default).
import { useCallback, useEffect, useState } from "react";

import { WorldRiskMap } from "@/components/map/WorldRiskMap";
import { Badge } from "@/components/ui";
import { GlobalEventTicker } from "@/features/terminal/GlobalEventTicker";
import { HazardToggle } from "@/features/terminal/HazardToggle";
import { PlaybackBar } from "@/features/terminal/PlaybackBar";
import { RegionBriefPanel } from "@/features/terminal/RegionBriefPanel";
import { usePlayback } from "@/features/terminal/usePlayback";
import { useTiles } from "@/features/terminal/useTiles";
import { WatchlistPanel } from "@/features/terminal/WatchlistPanel";
import { useTerminalStream } from "@/hooks/useV3Stream";
import { useWatchlistStore } from "@/stores/watchlistStore";
import { SCREENED_HAZARDS, type TileCell, type Viewport } from "@/types/tiles";
import type { CellBrief } from "@/types/cells";

export function TerminalPage() {
  const [viewport, setViewport] = useState<Viewport | null>(null);
  const [activeHazards, setActiveHazards] = useState<string[]>([...SCREENED_HAZARDS]);
  const [selectedCell, setSelectedCell] = useState<string | null>(null);
  const [focus, setFocus] = useState<{ lat: number; lon: number } | null>(null);

  const tiles = useTiles(viewport);
  const stream = useTerminalStream(viewport);
  const playback = usePlayback(viewport);
  const pin = useWatchlistStore((s) => s.pin);
  const unpin = useWatchlistStore((s) => s.unpin);
  const entries = useWatchlistStore((s) => s.entries);
  const updateScores = useWatchlistStore((s) => s.updateScores);
  const isPinned = (cellId: string) => entries.some((e) => e.cellId === cellId);

  // Freshest cells win: live frames when the stream has delivered, HTTP tiles otherwise.
  const liveCells: TileCell[] = stream.latest != null ? stream.cells : tiles.cells;
  // In replay the map paints the scrubbed historical frame instead of anything live.
  const cells: TileCell[] = playback.active ? playback.cells : liveCells;

  // Keep pinned entries' last-known headline scores fresh as *live* data flows through
  // (never from replay — a pin's headline must track now, not a past scrub position).
  useEffect(() => {
    if (playback.active || liveCells.length === 0) return;
    updateScores(Object.fromEntries(liveCells.map((c) => [c.cell_id, c.hazards])));
  }, [liveCells, playback.active, updateScores]);

  const onViewportChange = useCallback((v: Viewport) => setViewport(v), []);
  const onSelectCell = useCallback(
    (cell: { cellId: string }) => setSelectedCell(cell.cellId),
    [],
  );
  const focusEntry = useCallback((entry: { cellId: string; lat: number; lon: number }) => {
    setFocus({ lat: entry.lat, lon: entry.lon });
    setSelectedCell(entry.cellId);
  }, []);
  const togglePin = (brief: CellBrief) => {
    if (isPinned(brief.cell_id)) {
      unpin(brief.cell_id);
    } else {
      pin({
        cellId: brief.cell_id,
        lat: brief.lat,
        lon: brief.lon,
        lastHazards: brief.screening,
      });
    }
  };

  return (
    <div className="flex h-full flex-col">
      {/* Top strip: identity + stream state + hazard toggles */}
      <div className="flex items-center gap-3 border-b border-border bg-surface-2 px-4 py-2">
        <div className="leading-tight">
          <div className="text-sm font-bold tracking-[0.18em] text-glow">GLOBAL TERMINAL</div>
          <div className="text-2xs text-muted-2">
            multi-hazard screen · illustrative coefficients, uncalibrated
          </div>
        </div>
        <div className="ml-auto flex items-center gap-3">
          <HazardToggle active={activeHazards} onChange={setActiveHazards} />
          {playback.active ? (
            <Badge tone="warning">◀ replay mode</Badge>
          ) : (
            <>
              <button
                type="button"
                onClick={playback.enter}
                disabled={viewport == null}
                className="rounded border border-border-strong px-2 py-0.5 text-2xs font-semibold uppercase tracking-wide text-muted hover:bg-surface-3 hover:text-text disabled:opacity-40"
              >
                ◀ replay
              </button>
              <Badge tone={stream.connected ? "success" : "muted"}>
                {stream.connected ? "● stream live" : "stream offline"}
              </Badge>
            </>
          )}
        </div>
      </div>

      {/* Main panes */}
      <div className="flex min-h-0 flex-1">
        <div className="relative min-w-0 flex-1">
          <WorldRiskMap
            cells={cells}
            activeHazards={activeHazards}
            selectedCellId={selectedCell}
            onSelectCell={onSelectCell}
            onViewportChange={onViewportChange}
            focus={focus}
          />
          {/* Replay chrome: an unmissable amber inset ring + banner so the map can
              never be mistaken for live while scrubbing the past. */}
          {playback.active && (
            <>
              <div className="pointer-events-none absolute inset-0 z-10 ring-2 ring-inset ring-risk-high" />
              <div className="pointer-events-none absolute left-1/2 top-3 z-10 -translate-x-1/2 rounded-full border border-risk-high bg-bg/80 px-3 py-1 text-2xs font-bold uppercase tracking-[0.2em] text-risk-high backdrop-blur">
                ◀ Replay — {playback.currentTs ? playback.currentTs.slice(0, 16).replace("T", " ") + " UTC" : "…"}
              </div>
            </>
          )}
          <div className="pointer-events-none absolute left-3 top-3 z-10 rounded-full border border-border-strong bg-bg/70 px-2.5 py-1 text-2xs text-muted backdrop-blur">
            {cells.length} cells in view
            {tiles.resolution != null && ` · H3 res ${stream.latest?.resolution ?? tiles.resolution}`}
          </div>
        </div>

        <div className="flex w-96 shrink-0 flex-col gap-3 overflow-y-auto border-l border-border bg-surface-2 p-3">
          <WatchlistPanel onFocus={focusEntry} />
          {selectedCell && (
            <RegionBriefPanel
              cellId={selectedCell}
              pinned={isPinned(selectedCell)}
              onTogglePin={togglePin}
              onClose={() => setSelectedCell(null)}
            />
          )}
        </div>
      </div>

      {/* Edge strip: the scrub timeline in replay, the worldwide tape when live */}
      {playback.active ? (
        <PlaybackBar playback={playback} />
      ) : (
        <GlobalEventTicker events={stream.events} />
      )}
    </div>
  );
}
