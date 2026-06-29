// ProbabilityTimeline — how risk + confidence move over time as observations arrive
// (the points are accumulated client-side by useTwinStream from the WS broadcast).
// Recharts is already a dependency; a dual-axis line keeps risk (0–100) and
// confidence (0–100%) legible together.
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Badge, Card, CardHeader } from "@/components/ui";
import type { TimelinePoint } from "@/types/v2";

export function ProbabilityTimeline({
  points,
  live,
}: {
  points: TimelinePoint[];
  live: boolean;
}) {
  const data = points.map((p) => ({
    time: new Date(p.t).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }),
    risk: Number(p.risk.toFixed(1)),
    confidence: Number((p.confidence * 100).toFixed(1)),
  }));

  return (
    <Card>
      <CardHeader
        eyebrow="Probability Timeline"
        title="Risk & confidence over time"
        actions={
          <Badge tone={live ? "success" : "muted"}>{live ? "● live" : "offline"}</Badge>
        }
      />
      <p className="mt-1 text-xs text-muted">
        Updates as observations arrive over the live stream. Risk (0–100) and confidence (%)
        share the axis for comparison.
      </p>

      <div className="mt-3 h-56">
        {data.length <= 1 ? (
          <div className="flex h-full items-center justify-center text-xs text-muted-2">
            Awaiting observations… ingest a sensor reading or weather alert to populate the timeline.
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#ffffff14" />
              <XAxis dataKey="time" tick={{ fontSize: 10, fill: "#8b9196" }} />
              <YAxis domain={[0, 100]} tick={{ fontSize: 10, fill: "#8b9196" }} />
              <Tooltip
                contentStyle={{ background: "#0d1117", border: "1px solid #30363d", fontSize: 12 }}
              />
              <Line type="monotone" dataKey="risk" stroke="#ef4444" dot={false} strokeWidth={2} />
              <Line
                type="monotone"
                dataKey="confidence"
                stroke="#00ffd5"
                dot={false}
                strokeWidth={1.5}
                strokeDasharray="4 2"
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </Card>
  );
}
