import {
  Bar,
  BarChart,
  Cell,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { Driver } from "@/types/api";

// Horizontal bar of SHAP contributions: red bars raise risk, green bars lower it.
// This is the model's "why", straight from attribution — not a fabricated metric.
export function DriversChart({ drivers, height }: { drivers: Driver[]; height?: number }) {
  const data = drivers
    .map((d) => ({ name: d.name, contribution: Number(d.contribution.toFixed(3)) }))
    .sort((a, b) => Math.abs(b.contribution) - Math.abs(a.contribution));

  return (
    <ResponsiveContainer width="100%" height={height ?? Math.max(150, data.length * 40)}>
      <BarChart data={data} layout="vertical" margin={{ left: 8, right: 30, top: 4, bottom: 4 }}>
        <XAxis type="number" hide />
        <YAxis
          type="category"
          dataKey="name"
          width={150}
          tick={{ fill: "#9aa4b2", fontSize: 12 }}
          tickLine={false}
          axisLine={false}
        />
        <Tooltip
          cursor={{ fill: "rgba(255,255,255,0.04)" }}
          contentStyle={{ background: "#11161f", border: "1px solid #1e2733", borderRadius: 8 }}
          labelStyle={{ color: "#e6edf3" }}
          formatter={(v: number) => [v.toFixed(3), "SHAP contribution"]}
        />
        <Bar dataKey="contribution" radius={[3, 3, 3, 3]} barSize={15}>
          {data.map((d, i) => (
            <Cell key={i} fill={d.contribution >= 0 ? "#ef4444" : "#22c55e"} />
          ))}
          <LabelList
            dataKey="contribution"
            position="right"
            formatter={(v: number) => (v > 0 ? `+${v}` : `${v}`)}
            style={{ fill: "#9aa4b2", fontSize: 11 }}
          />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
