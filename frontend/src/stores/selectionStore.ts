// Cross-page selection state: which region is active, which analysis is being
// viewed, and which map cell is focused. This lets the Risk Intelligence map, the
// detail panel, and the report viewer stay in sync.
import { create } from "zustand";

interface SelectionState {
  regionKey: string;
  analysisId: string | null;
  selectedCellId: string | null;
  setRegion: (key: string) => void;
  setAnalysis: (id: string | null) => void;
  setCell: (id: string | null) => void;
}

export const useSelectionStore = create<SelectionState>((set) => ({
  regionKey: "liguria",
  analysisId: null,
  selectedCellId: null,
  setRegion: (regionKey) => set({ regionKey, selectedCellId: null }),
  setAnalysis: (analysisId) => set({ analysisId, selectedCellId: null }),
  setCell: (selectedCellId) => set({ selectedCellId }),
}));
