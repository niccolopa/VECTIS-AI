// Cell drill-down client — GET /api/v1/cells/{id}/brief.
import { http } from "@/services/apiClient";
import type { CellBrief } from "@/types/cells";

export function fetchCellBrief(cellId: string): Promise<CellBrief> {
  return http<CellBrief>(`/api/v1/cells/${encodeURIComponent(cellId)}/brief`);
}
