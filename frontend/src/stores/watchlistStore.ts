// Watchlist — the operator's pinned regions, persisted in localStorage so the list
// survives reloads. Each entry keeps the cell's coordinates (so a click can re-center
// the map even before any data loads) and the last-known per-hazard headline scores,
// refreshed whenever fresh tile/brief data passes through the terminal.
//
// Session 38: pins are synced (best-effort) to the backend attention registry, where
// the TierManager grants them a scheduled T1 refresh and T2 queue priority, and the
// eviction policy keeps them warm. Sync failure degrades to bookmark-only behavior.
// Priority buys freshness, not accuracy — the models stay uncalibrated either way.
import { create } from "zustand";
import { persist } from "zustand/middleware";

import { syncWatchlist } from "@/services/v3";
import { safeStorage } from "@/stores/selectionStore";

export interface WatchlistEntry {
  cellId: string;
  lat: number;
  lon: number;
  pinnedAt: string; // ISO
  /** Last-known per-hazard headline scores (0–100), refreshed as data flows. */
  lastHazards: Record<string, number>;
}

interface WatchlistState {
  entries: WatchlistEntry[];
  pin: (entry: Omit<WatchlistEntry, "pinnedAt">) => void;
  unpin: (cellId: string) => void;
  isPinned: (cellId: string) => boolean;
  /** Refresh the stored headline scores for any pinned cells present in `scores`. */
  updateScores: (scores: Record<string, Record<string, number>>) => void;
}

export const useWatchlistStore = create<WatchlistState>()(
  persist(
    (set, get) => ({
      entries: [],
      pin: (entry) => {
        set((s) => ({
          entries: s.entries.some((e) => e.cellId === entry.cellId)
            ? s.entries
            : [...s.entries, { ...entry, pinnedAt: new Date().toISOString() }],
        }));
        void syncWatchlist(get().entries.map((e) => e.cellId));
      },
      unpin: (cellId) => {
        set((s) => ({ entries: s.entries.filter((e) => e.cellId !== cellId) }));
        void syncWatchlist(get().entries.map((e) => e.cellId));
      },
      isPinned: (cellId) => get().entries.some((e) => e.cellId === cellId),
      updateScores: (scores) =>
        set((s) => {
          if (!s.entries.some((e) => scores[e.cellId])) return s; // nothing to refresh
          return {
            entries: s.entries.map((e) =>
              scores[e.cellId] ? { ...e, lastHazards: scores[e.cellId] } : e,
            ),
          };
        }),
    }),
    {
      name: "vectis-watchlist",
      storage: safeStorage,
      // Re-register persisted pins with the backend on load: attention is in-memory
      // server-side (expires with the viewer TTL), so a fresh page must re-announce.
      onRehydrateStorage: () => (state) => {
        if (state && state.entries.length > 0) {
          void syncWatchlist(state.entries.map((e) => e.cellId));
        }
      },
    },
  ),
);
