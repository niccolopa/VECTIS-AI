import type { ReactNode } from "react";
import { cn } from "@/utils/cn";

export function Spinner({ className }: { className?: string }) {
  return (
    <svg className={cn("animate-spin text-current", className)} viewBox="0 0 24 24" fill="none">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
      <path
        className="opacity-90"
        fill="currentColor"
        d="M4 12a8 8 0 018-8v3a5 5 0 00-5 5H4z"
      />
    </svg>
  );
}

export function LoadingState({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex h-full min-h-[160px] flex-col items-center justify-center gap-3 text-muted">
      <Spinner className="h-6 w-6 text-accent" />
      <span className="text-sm">{label}</span>
    </div>
  );
}

export function ErrorState({
  title = "Something went wrong",
  message,
  onRetry,
}: {
  title?: string;
  message?: string;
  onRetry?: () => void;
}) {
  return (
    <div className="flex h-full min-h-[160px] flex-col items-center justify-center gap-2 p-6 text-center">
      <div className="text-sm font-semibold text-risk-severe">⚠ {title}</div>
      {message && <p className="max-w-md text-xs text-muted">{message}</p>}
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-1 text-xs font-medium text-accent hover:underline"
        >
          Retry
        </button>
      )}
    </div>
  );
}

export function EmptyState({
  title,
  message,
  action,
}: {
  title: string;
  message?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex h-full min-h-[160px] flex-col items-center justify-center gap-2 p-6 text-center">
      <div className="text-sm font-semibold text-text">{title}</div>
      {message && <p className="max-w-md text-xs text-muted">{message}</p>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}
