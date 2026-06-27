import type { ReactNode } from "react";
import { cn } from "@/utils/cn";

export interface Column<T> {
  key: string;
  header: ReactNode;
  /** Cell renderer. */
  render: (row: T) => ReactNode;
  className?: string;
  align?: "left" | "right" | "center";
}

interface TableProps<T> {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  onRowClick?: (row: T) => void;
  isRowActive?: (row: T) => boolean;
  empty?: ReactNode;
}

export function Table<T>({
  columns,
  rows,
  rowKey,
  onRowClick,
  isRowActive,
  empty,
}: TableProps<T>) {
  const alignCls = (a?: string) =>
    a === "right" ? "text-right" : a === "center" ? "text-center" : "text-left";

  if (rows.length === 0 && empty) {
    return <div className="p-6">{empty}</div>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border">
            {columns.map((c) => (
              <th
                key={c.key}
                className={cn(
                  "px-4 py-2.5 font-medium text-2xs uppercase tracking-wide text-muted-2",
                  alignCls(c.align),
                  c.className,
                )}
              >
                {c.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={rowKey(row)}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
              className={cn(
                "border-b border-border/60 last:border-0",
                onRowClick && "cursor-pointer hover:bg-surface-3",
                isRowActive?.(row) && "bg-accent/10",
              )}
            >
              {columns.map((c) => (
                <td key={c.key} className={cn("px-4 py-2.5 text-text/90", alignCls(c.align), c.className)}>
                  {c.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
