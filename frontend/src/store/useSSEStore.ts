import { create } from "zustand";
import { connectSSE, disconnectSSE } from "../api/sse";

interface SSEState {
  eventSource: any | null; // 현재 SSE 연결 객체
  isConnected: boolean; // 연결 상태
  events: string[]; // 수신한 이벤트 로그

  connect: () => void;
  disconnect: () => void;
}

//SSE 연결 상태를 전역 관리하는 Zustand Store

export const useSSEStore = create<SSEState>((set, get) => ({
  eventSource: null,
  isConnected: false,
  events: [],

  // SSE 연결
  connect: () => {
    if (get().eventSource) return; // 중복 연결 방지

    const eventSource = connectSSE((event) => {
      const data = event.data;

      // 이벤트 수신 시 상태 업데이트
      set((state) => ({
        events: [...state.events, data],
      }));

      console.log("받은 SSE 데이터:", data);
    });

    if (eventSource) {
      set({ eventSource, isConnected: true });
    }
  },

  // SSE 연결 종료
  disconnect: () => {
    const { eventSource } = get();
    disconnectSSE(eventSource);
    set({ eventSource: null, isConnected: false });
  },
}));
