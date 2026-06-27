// Datasets "client". NOTE: backed by MOCK data (no backend endpoint yet) — see
// ./mocks/datasets.ts. Shaped as an async API so hooks/UI treat it uniformly and
// swapping in a real endpoint later is a one-line change.
import { DATASETS_ARE_MOCK, MOCK_DATASETS, type DatasetEntry } from "@/services/mocks/datasets";

export type { DatasetEntry };

export const datasetsApi = {
  isMock: DATASETS_ARE_MOCK,
  list: async (): Promise<DatasetEntry[]> => MOCK_DATASETS,
};
