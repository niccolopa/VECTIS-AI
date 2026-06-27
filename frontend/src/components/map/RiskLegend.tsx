import { RISK_COLORS } from "@/utils/risk";

const ITEMS: Array<[string, string]> = [
  [RISK_COLORS.low, "Low"],
  [RISK_COLORS.moderate, "Moderate"],
  [RISK_COLORS.high, "High"],
  [RISK_COLORS.severe, "Severe"],
];

export function RiskLegend() {
  return (
    <div className="flex gap-3 rounded-lg border border-border bg-surface-2/90 px-3 py-2 text-2xs text-muted backdrop-blur">
      {ITEMS.map(([color, label]) => (
        <span key={label} className="flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full" style={{ background: color }} />
          {label}
        </span>
      ))}
    </div>
  );
}
