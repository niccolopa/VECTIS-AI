import { NavLink } from "react-router-dom";
import { NAV_ITEMS } from "@/components/layout/nav";
import { useUiStore } from "@/stores/uiStore";
import { cn } from "@/utils/cn";

export function Sidebar() {
  const collapsed = useUiStore((s) => s.sidebarCollapsed);

  return (
    <aside
      className={cn(
        "flex h-full flex-col border-r border-border bg-surface-2 transition-[width] duration-200",
        collapsed ? "w-16" : "w-60",
      )}
    >
      <div className="flex h-14 items-center gap-2.5 px-4 border-b border-border">
        <span className="text-accent text-lg leading-none text-glow-cyan">▲</span>
        {!collapsed && (
          <div className="leading-tight">
            <div className="text-sm font-bold tracking-[0.18em] text-glow">VECTIS</div>
            <div className="text-2xs text-muted-2">Decision Intelligence</div>
          </div>
        )}
      </div>

      <nav className="flex-1 space-y-1 p-2">
        {NAV_ITEMS.map(({ to, label, icon: Icon, section }) => (
          <div key={to}>
            {section && !collapsed && (
              <div className="mt-4 mb-1 px-3 pt-2 border-t border-border text-2xs uppercase tracking-wider text-muted-2">
                {section}
              </div>
            )}
            {section && collapsed && <div className="my-2 mx-2 border-t border-border" />}
            <NavLink
              to={to}
              end={to === "/"}
              title={collapsed ? label : undefined}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors",
                  collapsed && "justify-center px-0",
                  isActive
                    ? "bg-accent/15 text-accent"
                    : "text-muted hover:bg-surface-3 hover:text-text",
                )
              }
            >
              <Icon className="shrink-0" />
              {!collapsed && <span className="truncate">{label}</span>}
            </NavLink>
          </div>
        ))}
      </nav>

      {!collapsed && (
        <div className="border-t border-border p-3 text-2xs text-muted-2">
          VECTIS v1.0 · Climate Risk
        </div>
      )}
    </aside>
  );
}
