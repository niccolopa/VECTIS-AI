import type { ReactNode } from "react";
import { cn } from "@/utils/cn";

export function PageContainer({
  children,
  className,
  full,
}: {
  children: ReactNode;
  className?: string;
  /** Full-height flex column (for map-heavy pages). */
  full?: boolean;
}) {
  return (
    <div className={cn("p-5", full ? "flex h-full flex-col" : "", className)}>{children}</div>
  );
}

export function PageHeader({
  title,
  subtitle,
  actions,
}: {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="mb-4 flex items-start justify-between gap-4">
      <div>
        <h2 className="text-lg font-semibold">{title}</h2>
        {subtitle && <p className="mt-0.5 text-sm text-muted">{subtitle}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}
