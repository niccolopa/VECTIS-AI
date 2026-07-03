// GlobalEventTicker — the tape. A single edge strip of the newest real detections
// worldwide (FIRMS fires, USGS quakes, GDACS alerts, weather), fed by the terminal
// stream's *global* event batch — deliberately NOT viewport-filtered: the map shows
// where you're looking, the tape shows what the planet is doing.
//
// Reuses the Session-24 EventFeed pattern: the hook caps its rolling buffer, and this
// also slices defensively (`max`) so the DOM never grows unbounded however fast the
// stream runs.
import type { V3Event } from "@/types/v3";

// Source accents — EventFeed's palette extended with the Session-31 global feeds.
const SOURCE_COLOR: Record<string, string> = {
  weather_api: "#00ffd5",
  nasa_firms: "#f59e0b",
  usgs_quake: "#c084fc",
  gdacs: "#38bdf8",
};

function clock(iso: string): string {
  return new Date(iso).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}

export function GlobalEventTicker({ events, max = 50 }: { events: V3Event[]; max?: number }) {
  const rows = events.slice(0, max);
  return (
    <div
      data-testid="global-event-ticker"
      className="flex h-9 items-center gap-2 overflow-hidden border-t border-border bg-surface-2 px-3 font-sans text-2xs"
    >
      <span className="shrink-0 uppercase tracking-widest text-muted-2">Global tape</span>
      <span className="shrink-0 text-border-strong">|</span>
      {rows.length === 0 ? (
        <span className="text-muted-2">Awaiting worldwide detections…</span>
      ) : (
        <div className="flex items-center gap-5 overflow-x-auto whitespace-nowrap [scrollbar-width:none]">
          {rows.map((e) => (
            <span key={e.event_id} className="flex items-center gap-1.5">
              <span className="text-muted-2">{clock(e.observed_at)}</span>
              <span style={{ color: SOURCE_COLOR[e.source] ?? "#8b9196" }}>
                {e.source.toUpperCase()}
              </span>
              <span className="text-muted">{e.variable}</span>
              <span className="tabular-nums text-text">{e.value}</span>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
