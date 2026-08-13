"use client";

import { create } from "zustand";
import { apiFetch } from "@/lib/api";

type ActiveCase = {
  case_id: string;
  title?: string;
  lead_investigator?: string;
  status?: string;
};

type UiState = {
  sidebarOpen: boolean;
  activeCase: ActiveCase | null;
  caseLoaded: boolean;
  toggleSidebar: () => void;
  setSidebarOpen: (open: boolean) => void;
  hydrateSidebar: () => void;
  refreshActiveCase: () => Promise<void>;
};

export const useUiStore = create<UiState>((set, get) => ({
  sidebarOpen: true,
  activeCase: null,
  caseLoaded: false,
  toggleSidebar: () => {
    const next = !get().sidebarOpen;
    set({ sidebarOpen: next });
    try {
      localStorage.setItem("erakshak.sidebarOpen", next ? "1" : "0");
    } catch {
      /* ignore */
    }
  },
  setSidebarOpen: (open) => {
    set({ sidebarOpen: open });
    try {
      localStorage.setItem("erakshak.sidebarOpen", open ? "1" : "0");
    } catch {
      /* ignore */
    }
  },
  hydrateSidebar: () => {
    try {
      const raw = localStorage.getItem("erakshak.sidebarOpen");
      if (raw === "0") set({ sidebarOpen: false });
      if (raw === "1") set({ sidebarOpen: true });
    } catch {
      /* ignore */
    }
  },
  refreshActiveCase: async () => {
    try {
      const data = await apiFetch<{ case: ActiveCase }>("/api/cases/active");
      set({ activeCase: data.case, caseLoaded: true });
    } catch {
      set({ activeCase: null, caseLoaded: true });
    }
  },
}));
