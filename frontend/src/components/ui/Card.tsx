import type { ReactNode } from "react";
import { cn } from "@/utils/cn";

interface CardProps {
  children: ReactNode;
  className?: string;
  /** Removes default padding (e.g. when embedding a map or table edge-to-edge). */
  flush?: boolean;
}

export function Card({ children, className, flush }: CardProps) {
  return (
    <div
      className={cn(
        "rounded-xl border border-border bg-surface overflow-hidden",
        !flush && "p-4",
        className,
      )}
    >
      {children}
    </div>
  );
}

interface CardHeaderProps {
  title: ReactNode;
  eyebrow?: ReactNode;
  actions?: ReactNode;
  className?: string;
}

export function CardHeader({ title, eyebrow, actions, className }: CardHeaderProps) {
  return (
    <div className={cn("flex items-start justify-between gap-3", className)}>
      <div>
        {eyebrow && <div className="eyebrow mb-0.5">{eyebrow}</div>}
        <h3 className="text-sm font-semibold text-text">{title}</h3>
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}
