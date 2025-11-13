import { create } from "zustand";
import { persist } from "zustand/middleware";

interface SSEEventsState {
  events: string[];
  addEvent: (e: string) => void;
  clearEvents: () => void;
}

export const useSSEEventsStore = create(
  persist<SSEEventsState>(
    (set) => ({
      events: [],
      addEvent: (e: string) =>
        set((state) => ({ events: [...state.events, e] })),
      clearEvents: () => set({ events: [] }),
    }),
    {
      name: "sse-events-store",
    }
  )
);
