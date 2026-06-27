import type { ButtonHTMLAttributes, ReactNode } from "react";
import { cn } from "@/utils/cn";
import { Spinner } from "@/components/ui/states";

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "sm" | "md";

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  icon?: ReactNode;
}

const VARIANTS: Record<Variant, string> = {
  primary: "bg-accent border-accent text-white hover:bg-accent/90",
  secondary: "bg-surface border-border text-text hover:bg-surface-3",
  ghost: "bg-transparent border-transparent text-muted hover:text-text hover:bg-surface-3",
  danger: "bg-risk-severe/15 border-risk-severe/40 text-risk-severe hover:bg-risk-severe/25",
};

const SIZES: Record<Size, string> = {
  sm: "h-8 px-3 text-xs gap-1.5",
  md: "h-9 px-4 text-sm gap-2",
};

export function Button({
  variant = "secondary",
  size = "md",
  loading = false,
  icon,
  className,
  children,
  disabled,
  ...rest
}: Props) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center rounded-lg border font-medium transition-colors",
        "disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-accent/50",
        VARIANTS[variant],
        SIZES[size],
        className,
      )}
      disabled={disabled || loading}
      {...rest}
    >
      {loading ? <Spinner className="h-4 w-4" /> : icon}
      {children}
    </button>
  );
}
