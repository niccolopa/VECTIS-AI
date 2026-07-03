// Cross-page selection state: which region is active, which analysis is being
// viewed, and which map cell is focused. This lets the Risk Intelligence map, the
// detail panel, and the report viewer stay in sync.
import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

export const DEFAULT_REGION = "california";

// localStorage can be missing or throw (SSR, tests, Safari private mode). Fall
// back to an in-memory store so persistence degrades silently, never crashes.
// Shared with every persisted store (selection, watchlist).
const memory = new Map<string, string>();
export const safeStorage = createJSONStorage(() => {
  try {
    if (typeof window !== "undefined" && window.localStorage) return window.localStorage;
  } catch {
    /* access denied — fall through */
  }
  return {
    getItem: (k: string) => memory.get(k) ?? null,
    setItem: (k: string, v: string) => void memory.set(k, v),
    removeItem: (k: string) => void memory.delete(k),
  };
});

interface SelectionState {
  regionKey: string;
  analysisId: string | null;
  selectedCellId: string | null;
  setRegion: (key: string) => void;
  setAnalysis: (id: string | null) => void;
  setCell: (id: string | null) => void;
}

export const useSelectionStore = create<SelectionState>()(
  persist(
    (set) => ({
      regionKey: DEFAULT_REGION,
      analysisId: null,
      selectedCellId: null,
      setRegion: (regionKey) => set({ regionKey, selectedCellId: null }),
      setAnalysis: (analysisId) => set({ analysisId, selectedCellId: null }),
      setCell: (selectedCellId) => set({ selectedCellId }),
    }),
    // Only the region is worth persisting; analysis/cell are per-session.
    {
      name: "vectis-selection",
      storage: safeStorage,
      partialize: (s) => ({ regionKey: s.regionKey }),
    },
  ),
);
