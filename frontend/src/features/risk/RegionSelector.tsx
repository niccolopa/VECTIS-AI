import { useRegions } from "@/hooks/queries";

interface Props {
  value: string;
  onChange: (key: string) => void;
}

// Region picker driven by the real /api/v1/regions endpoint (no hardcoded list).
export function RegionSelector({ value, onChange }: Props) {
  const { data: regions = [], isLoading } = useRegions();
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      disabled={isLoading}
      className="h-9 rounded-lg border border-border bg-surface px-3 text-sm text-text focus:outline-none focus:ring-2 focus:ring-accent/50"
    >
      {regions.map((r) => (
        <option key={r.key} value={r.key}>
          {r.label}
        </option>
      ))}
    </select>
  );
}
