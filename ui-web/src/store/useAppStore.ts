import { create } from 'zustand';

interface AppState {
  currentRunId: string | null;
  selectedModel: string | null;
  hardwareTier: string | null;
  setCurrentRunId: (runId: string | null) => void;
  setSelectedModel: (model: string | null) => void;
  setHardwareTier: (tier: string | null) => void;
  reset: () => void;
}

export const useAppStore = create<AppState>((set) => ({
  currentRunId: null,
  selectedModel: null,
  hardwareTier: null,
  setCurrentRunId: (runId) => set({ currentRunId: runId }),
  setSelectedModel: (model) => set({ selectedModel: model }),
  setHardwareTier: (tier) => set({ hardwareTier: tier }),
  reset: () => set({ currentRunId: null, selectedModel: null, hardwareTier: null }),
}));
