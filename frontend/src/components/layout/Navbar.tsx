import { useLocation } from "react-router-dom";
import { IconActivity, IconMenu } from "@/components/layout/icons";
import { NAV_ITEMS } from "@/components/layout/nav";
import { useUiStore } from "@/stores/uiStore";
import { useHealth } from "@/hooks/queries";
import { cn } from "@/utils/cn";

function useSectionTitle(): string {
  const { pathname } = useLocation();
  const match = NAV_ITEMS.filter((n) => n.to !== "/").find((n) => pathname.startsWith(n.to));
  if (match) return match.label;
  return pathname === "/" ? "Overview" : "VECTIS";
}

export function Navbar() {
  const toggle = useUiStore((s) => s.toggleSidebar);
  const title = useSectionTitle();
  const { data: health, isError } = useHealth();
  const online = !!health && !isError;

  return (
    <header className="flex h-14 items-center justify-between border-b border-border bg-surface-2 px-4">
      <div className="flex items-center gap-3">
        <button
          onClick={toggle}
          className="rounded-lg p-1.5 text-muted hover:bg-surface-3 hover:text-text"
          aria-label="Toggle sidebar"
        >
          <IconMenu />
        </button>
        <div>
          <div className="eyebrow">Operational Intelligence</div>
          <h1 className="text-sm font-semibold leading-tight text-glow">{title}</h1>
        </div>
      </div>

      <div className="flex items-center gap-4 text-xs">
        {health && (
          <span className="hidden items-center gap-1.5 text-muted sm:flex">
            <IconActivity className="h-3.5 w-3.5" />
            engine: {health.llm_provider} · {health.env}
          </span>
        )}
        <span className="flex items-center gap-1.5 text-muted">
          <span
            className={cn(
              "h-2 w-2 rounded-full",
              online ? "bg-risk-low" : "bg-risk-severe",
            )}
          />
          {online ? `API online · v${health?.version}` : "API offline"}
        </span>
      </div>
    </header>
  );
}
