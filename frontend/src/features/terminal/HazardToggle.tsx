// HazardToggle — per-hazard layer switches for the world map. The first genuinely
// multi-hazard visual control in the console: an operator isolates one hazard or
// composites several; the map repaints instantly (client-side max, no refetch).
import { SCREENED_HAZARDS, type Hazard } from "@/types/tiles";
import { cn } from "@/utils/cn";

export const HAZARD_META: Record<Hazard, { label: string; color: string }> = {
  wildfire: { label: "Fire", color: "#f59e0b" },
  flood: { label: "Flood", color: "#38bdf8" },
  quake: { label: "Quake", color: "#c084fc" },
  cyclone: { label: "Cyclone", color: "#2dd4bf" },
};

export function HazardToggle({
  active,
  onChange,
}: {
  active: string[];
  onChange: (next: string[]) => void;
}) {
  const toggle = (hazard: Hazard) =>
    onChange(
      active.includes(hazard) ? active.filter((h) => h !== hazard) : [...active, hazard],
    );

  return (
    <div className="flex items-center gap-1 rounded-full border border-border-strong bg-bg/70 p-1 backdrop-blur">
      {SCREENED_HAZARDS.map((hazard) => {
        const on = active.includes(hazard);
        const meta = HAZARD_META[hazard];
        return (
          <button
            key={hazard}
            type="button"
            aria-pressed={on}
            onClick={() => toggle(hazard)}
            className={cn(
              "rounded-full px-2.5 py-1 text-2xs uppercase tracking-wide transition-colors",
              on ? "text-bg" : "text-muted-2 hover:text-text",
            )}
            style={on ? { background: meta.color } : undefined}
          >
            {meta.label}
          </button>
        );
      })}
    </div>
  );
}
