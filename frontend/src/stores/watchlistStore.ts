// Watchlist — the operator's pinned regions, persisted in localStorage so the list
// survives reloads. Each entry keeps the cell's coordinates (so a click can re-center
// the map even before any data loads) and the last-known per-hazard headline scores,
// refreshed whenever fresh tile/brief data passes through the terminal.
//
// NOTE (Session 38 — Demand-Driven Compute): pinned cells do NOT yet receive compute
// priority in the backend TierManager. Pinning is purely a UI bookmark today; wiring
// watchlist entries into the promotion queues is explicitly Session 38's job. Nothing
// here fakes that behavior.
import { create } from "zustand";
import { persist } from "zustand/middleware";

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
      pin: (entry) =>
        set((s) => ({
          entries: s.entries.some((e) => e.cellId === entry.cellId)
            ? s.entries
            : [...s.entries, { ...entry, pinnedAt: new Date().toISOString() }],
        })),
      unpin: (cellId) =>
        set((s) => ({ entries: s.entries.filter((e) => e.cellId !== cellId) })),
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
    { name: "vectis-watchlist", storage: safeStorage },
  ),
);
