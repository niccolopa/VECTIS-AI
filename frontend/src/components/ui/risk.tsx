import { cn } from "@/utils/cn";
import { bandColor, bandLabel } from "@/utils/risk";
import type { RiskBand } from "@/types/api";

export function RiskBadge({ band, className }: { band: RiskBand; className?: string }) {
  const color = bandColor(band);
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2 py-0.5 text-2xs font-semibold uppercase tracking-wide",
        className,
      )}
      style={{ color, borderColor: `${color}55`, background: `${color}1f` }}
    >
      {bandLabel(band)}
    </span>
  );
}

export function RiskScore({
  score,
  band,
  size = "md",
}: {
  score: number;
  band: RiskBand;
  size?: "sm" | "md" | "lg";
}) {
  const color = bandColor(band);
  const sizes = { sm: "text-xl", md: "text-3xl", lg: "text-5xl" };
  return (
    <span className="inline-flex items-baseline gap-1 tabular-nums">
      <span className={cn("font-bold leading-none", sizes[size])} style={{ color }}>
        {score.toFixed(0)}
      </span>
      <span className="text-xs text-muted">/100</span>
    </span>
  );
}

export function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-surface-3">
        <div className="h-full rounded-full bg-accent" style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs tabular-nums text-muted">{pct}%</span>
    </div>
  );
}
