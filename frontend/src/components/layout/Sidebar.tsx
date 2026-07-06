import { NavLink, useLocation } from "react-router-dom";
import { NAV_ITEMS, type NavItem } from "@/components/layout/nav";
import { useUiStore } from "@/stores/uiStore";
import { cn } from "@/utils/cn";

export function Sidebar() {
  const collapsed = useUiStore((s) => s.sidebarCollapsed);
  const { pathname } = useLocation();

  // Primary platform items vs the secondary "Origin Demo" archive: the first
  // item carrying a `section` marker starts the archive group.
  const splitAt = NAV_ITEMS.findIndex((i) => i.section);
  const primary = splitAt === -1 ? NAV_ITEMS : NAV_ITEMS.slice(0, splitAt);
  const archive = splitAt === -1 ? [] : NAV_ITEMS.slice(splitAt);
  // Collapsed by default; forced open while the viewer is actually on an
  // archive route (never hide the active link), user-toggleable otherwise.
  const onArchiveRoute = archive.some((i) => pathname.startsWith(i.to));

  const link = ({ to, label, icon: Icon }: NavItem, dim = false) => (
    <NavLink
      key={to}
      to={to}
      end={to === "/"}
      title={collapsed ? label : undefined}
      className={({ isActive }) =>
        cn(
          "flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors",
          collapsed && "justify-center px-0",
          isActive
            ? "bg-accent/15 text-accent"
            : dim
              ? "text-muted-2 hover:bg-surface-3 hover:text-muted"
              : "text-muted hover:bg-surface-3 hover:text-text",
        )
      }
    >
      <Icon className="shrink-0" />
      {!collapsed && <span className="truncate">{label}</span>}
    </NavLink>
  );

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
        {primary.map((item) => link(item))}

        {archive.length > 0 && (
          <div className="mt-4 border-t border-border pt-2">
            {collapsed ? (
              // Icon-only sidebar: no summary text to toggle, just the dimmed links.
              archive.map((item) => link(item, true))
            ) : (
              <details className="group" open={onArchiveRoute || undefined}>
                <summary className="cursor-pointer select-none list-none px-3 py-1 text-2xs uppercase tracking-wider text-muted-2 hover:text-muted">
                  <span className="mr-1 inline-block transition-transform group-open:rotate-90">▸</span>
                  {archive[0].section}
                </summary>
                <div className="mt-1 space-y-1">{archive.map((item) => link(item, true))}</div>
              </details>
            )}
          </div>
        )}
      </nav>

      {!collapsed && (
        <div className="border-t border-border p-3 text-2xs text-muted-2">
          VECTIS v1.0 · Climate Risk
        </div>
      )}
    </aside>
  );
}
