import type { ReactNode } from "react";
import { Card } from "@/components/ui/Card";

interface StatCardProps {
  label: string;
  value: ReactNode;
  sub?: ReactNode;
  accent?: string;
}

export function StatCard({ label, value, sub, accent }: StatCardProps) {
  return (
    <Card>
      <div className="eyebrow">{label}</div>
      <div className="mt-1 text-2xl font-bold tabular-nums" style={accent ? { color: accent } : undefined}>
        {value}
      </div>
      {sub && <div className="mt-0.5 text-xs text-muted">{sub}</div>}
    </Card>
  );
}
