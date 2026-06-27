// Client UI state (not server data). Kept deliberately small — server state lives
// in TanStack Query, not here.
import { create } from "zustand";

interface UiState {
  sidebarCollapsed: boolean;
  toggleSidebar: () => void;
  setSidebar: (collapsed: boolean) => void;
}

export const useUiStore = create<UiState>((set) => ({
  sidebarCollapsed: false,
  toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
  setSidebar: (collapsed) => set({ sidebarCollapsed: collapsed }),
}));
