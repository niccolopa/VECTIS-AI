import type { ReactNode } from "react";
import { cn } from "@/utils/cn";

type Tone = "default" | "accent" | "success" | "warning" | "danger" | "muted";

const TONES: Record<Tone, string> = {
  default: "bg-surface-3 text-text border-border-strong",
  accent: "bg-accent/15 text-accent border-accent/30",
  success: "bg-risk-low/15 text-risk-low border-risk-low/30",
  warning: "bg-risk-high/15 text-risk-high border-risk-high/30",
  danger: "bg-risk-severe/15 text-risk-severe border-risk-severe/30",
  muted: "bg-surface-2 text-muted border-border",
};

export function Badge({
  children,
  tone = "default",
  className,
}: {
  children: ReactNode;
  tone?: Tone;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2 py-0.5 text-2xs font-semibold uppercase tracking-wide",
        TONES[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}
