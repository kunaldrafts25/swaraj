import { create } from 'zustand';
import type { AgentPlan, PlannedStep, Observation, ValidationError } from '../lib/types';

interface TraceState {
  plan: AgentPlan | null;
  steps: PlannedStep[];
  observations: Observation[];
  selfCheckErrors: ValidationError[];
  currentIteration: number;
  addStep: (step: PlannedStep) => void;
  addObservation: (observation: Observation) => void;
  setSelfCheckErrors: (errors: ValidationError[]) => void;
  setIteration: (iteration: number) => void;
  reset: () => void;
}

export const useTraceStore = create<TraceState>((set) => ({
  plan: null,
  steps: [],
  observations: [],
  selfCheckErrors: [],
  currentIteration: 0,
  addStep: (step) => set((state) => ({ steps: [...state.steps, step] })),
  addObservation: (observation) => set((state) => ({ observations: [...state.observations, observation] })),
  setSelfCheckErrors: (errors) => set({ selfCheckErrors: errors }),
  setIteration: (iteration) => set({ currentIteration: iteration }),
  reset: () => set({ plan: null, steps: [], observations: [], selfCheckErrors: [], currentIteration: 0 }),
}));
