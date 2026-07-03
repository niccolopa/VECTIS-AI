// WatchlistPanel — the operator's pinned regions. Each row shows the cell's
// last-known headline score per hazard; clicking a row re-centers the map on the
// cell and opens its drill-down brief. Pin/unpin from here or from the brief panel.
//
// Watchlist entries do NOT yet receive compute priority in TierManager — that
// wiring is Session 38 (see stores/watchlistStore.ts). This panel is a bookmark
// surface, and presents itself as nothing more.
import { Badge, Card, CardHeader } from "@/components/ui";
import { HAZARD_META } from "@/features/terminal/HazardToggle";
import { useWatchlistStore } from "@/stores/watchlistStore";
import type { Hazard } from "@/types/tiles";
import { riskColor } from "@/utils/risk";

export function WatchlistPanel({
  onFocus,
}: {
  onFocus: (entry: { cellId: string; lat: number; lon: number }) => void;
}) {
  const entries = useWatchlistStore((s) => s.entries);
  const unpin = useWatchlistStore((s) => s.unpin);

  return (
    <Card flush>
      <div className="border-b border-border px-4 py-3">
        <CardHeader
          eyebrow="Watchlist"
          title="Pinned regions"
          actions={<Badge tone="muted">{entries.length}</Badge>}
        />
      </div>
      <div className="max-h-72 overflow-y-auto px-2 py-1">
        {entries.length === 0 ? (
          <div className="px-2 py-6 text-center text-2xs text-muted-2">
            Nothing pinned — open a cell's brief and pin it to watch it here.
          </div>
        ) : (
          entries.map((e) => (
            <div
              key={e.cellId}
              className="group flex items-center gap-2 rounded px-2 py-1.5 hover:bg-surface-3"
            >
              <button
                type="button"
                onClick={() => onFocus(e)}
                className="flex min-w-0 flex-1 items-center gap-2 text-left"
                title={`Re-center on ${e.cellId}`}
              >
                <span className="truncate font-sans text-2xs text-text">{e.cellId}</span>
                <span className="ml-auto flex shrink-0 items-center gap-1.5 tabular-nums">
                  {Object.entries(e.lastHazards).map(([hazard, score]) => {
                    const meta = HAZARD_META[hazard as Hazard] ?? { label: hazard };
                    return (
                      <span key={hazard} className="text-2xs" title={`${meta.label} ${score.toFixed(0)}`}>
                        <span className="text-muted-2">{meta.label.slice(0, 2).toUpperCase()}</span>{" "}
                        <span style={{ color: riskColor(score) }}>{score.toFixed(0)}</span>
                      </span>
                    );
                  })}
                </span>
              </button>
              <button
                type="button"
                onClick={() => unpin(e.cellId)}
                aria-label={`Unpin ${e.cellId}`}
                className="shrink-0 text-2xs text-muted-2 opacity-0 transition-opacity hover:text-text group-hover:opacity-100"
              >
                ✕
              </button>
            </div>
          ))
        )}
      </div>
      <div className="border-t border-border px-4 py-2 text-2xs text-muted-2">
        Pins are bookmarks — compute prioritization for pinned regions lands in Session 38.
      </div>
    </Card>
  );
}
