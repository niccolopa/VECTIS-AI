// RiskEvolutionTimeline — risk and confidence scrolling over time as frames arrive.
// Recharts (already a dependency) with a true dual axis: risk (0–100) on the left,
// confidence (0–100%) on the right, so both trends stay legible at their own scale.
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
import type { V3TimelinePoint } from "@/types/v3";

export function RiskEvolutionTimeline({
  points,
  live,
}: {
  points: V3TimelinePoint[];
  live: boolean;
}) {
  const data = points.map((p) => ({
    time: new Date(p.t).toLocaleTimeString([], { minute: "2-digit", second: "2-digit" }),
    risk: Number(p.risk.toFixed(1)),
    confidence: Number((p.confidence * 100).toFixed(1)),
  }));

  return (
    <Card>
      <CardHeader
        eyebrow="Risk Evolution"
        title="Risk & confidence over time"
        actions={<Badge tone={live ? "success" : "muted"}>{live ? "● live" : "offline"}</Badge>}
      />
      <div className="mt-3 h-56">
        {data.length <= 1 ? (
          <div className="flex h-full items-center justify-center text-xs text-muted-2">
            Awaiting the live stream…
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 8, right: 4, bottom: 0, left: -16 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#ffffff14" />
              <XAxis dataKey="time" tick={{ fontSize: 10, fill: "#8b9196" }} minTickGap={24} />
              <YAxis yAxisId="risk" domain={[0, 100]} tick={{ fontSize: 10, fill: "#8b9196" }} />
              <YAxis
                yAxisId="conf"
                orientation="right"
                domain={[0, 100]}
                tick={{ fontSize: 10, fill: "#00ffd5" }}
              />
              <Tooltip
                contentStyle={{ background: "#0d1117", border: "1px solid #30363d", fontSize: 12 }}
              />
              <Line
                yAxisId="risk"
                type="monotone"
                dataKey="risk"
                stroke="#ef4444"
                dot={false}
                strokeWidth={2}
                isAnimationActive={false}
              />
              <Line
                yAxisId="conf"
                type="monotone"
                dataKey="confidence"
                stroke="#00ffd5"
                dot={false}
                strokeWidth={1.5}
                strokeDasharray="4 2"
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </Card>
  );
}
