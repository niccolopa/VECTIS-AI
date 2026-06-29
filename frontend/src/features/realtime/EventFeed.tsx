// EventFeed — a rolling, terminal-style log of the normalized events driving the
// changes. The hook already caps its buffer; this also slices defensively so the DOM
// never grows unbounded no matter how fast the stream runs (`max`, default 50 rows).
import { Card, CardHeader } from "@/components/ui";
import type { V3Event } from "@/types/v3";

const SOURCE_COLOR: Record<string, string> = {
  weather_api: "#00ffd5",
  nasa_firms: "#f59e0b",
};

function clock(iso: string): string {
  return new Date(iso).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}

export function EventFeed({ events, max = 50 }: { events: V3Event[]; max?: number }) {
  const rows = events.slice(0, max);
  return (
    <Card flush>
      <div className="border-b border-border px-4 py-3">
        <CardHeader eyebrow="Raw Event Feed" title="Normalized observations" />
      </div>
      <div className="h-72 overflow-y-auto px-4 py-2 font-sans text-2xs leading-relaxed">
        {rows.length === 0 ? (
          <div className="py-8 text-center text-muted-2">Awaiting the live stream…</div>
        ) : (
          rows.map((e) => (
            <div key={e.event_id} className="flex items-center gap-2 whitespace-nowrap py-0.5">
              <span className="text-muted-2">{clock(e.observed_at)}</span>
              <span style={{ color: SOURCE_COLOR[e.source] ?? "#8b9196" }}>
                {e.source.toUpperCase()}
              </span>
              <span className="text-muted">{e.variable}</span>
              <span className="tabular-nums text-text">{e.value}</span>
            </div>
          ))
        )}
      </div>
    </Card>
  );
}
