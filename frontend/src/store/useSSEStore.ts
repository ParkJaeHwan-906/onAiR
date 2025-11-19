import { create } from "zustand";
import { connectSSE, disconnectSSE } from "../api/sse";
import { useSSEEventsStore } from "./useSSEEventsStore";

interface SSEState {
  eventSource: any | null; // 현재 SSE 연결 객체
  isConnected: boolean; // 연결 상태
  events: string[]; // 수신한 이벤트 로그
  reconnectAttempts: number; // 재연결 시도 횟수

  connect: () => void;
  disconnect: () => void;
}

//SSE 연결 상태를 전역 관리하는 Zustand Store

export const useSSEStore = create<SSEState>((set, get) => ({
  eventSource: null,
  isConnected: false,
  events: [],
  reconnectAttempts: 0,

  // SSE 연결
  connect: () => {
    // 이미 연결되어 있고 활성 상태면 재연결하지 않음
    const currentEventSource = get().eventSource;
    if (currentEventSource) {
      const readyState = currentEventSource.readyState;
      // console.log("🔍 기존 SSE 연결 상태:", readyState, {
      //   CONNECTING: EventSource.CONNECTING,
      //   OPEN: EventSource.OPEN,
      //   CLOSED: EventSource.CLOSED
      // });

      // CONNECTING 상태면 대기
      if (readyState === EventSource.CONNECTING) return;
      // OPEN 상태면 이미 연결됨
      if (readyState === EventSource.OPEN) return;
    }

    const eventSource = connectSSE(
      (event) => {
        const data = event.data;

        // 이벤트 수신 시 상태 업데이트
        set((state) => ({
          events: [...state.events, data],
          isConnected: true,
          reconnectAttempts: 0,
        }));
        useSSEEventsStore.getState().addEvent(data);
      },
      (attempt) => {
        // // 재연결 시도 중
        set({
          isConnected: false,
          reconnectAttempts: attempt,
        });
      },
      (_error) => {
        // // 재연결 실패
        // console.error("❌ useSSEStore - 재연결 실패:", error);
        set({
          isConnected: false,
          reconnectAttempts: 0,
        });
      }
    );

    if (eventSource) {
      // 연결 상태 확인
      const initialState = eventSource.readyState === EventSource.OPEN;

      set({
        eventSource,
        isConnected: initialState,
        reconnectAttempts: 0,
      });

      // onopen 이벤트 리스너 추가 (연결 완료 시 isConnected 업데이트)

      const originalOnOpen = eventSource.onopen;
      eventSource.onopen = (event: any) => {
        set({
          isConnected: true,
          reconnectAttempts: 0,
        });
        if (originalOnOpen) originalOnOpen(event);
      };
    }
  },

  // SSE 연결 종료
  disconnect: () => {
    const { eventSource } = get();
    disconnectSSE(eventSource);
    set({
      eventSource: null,
      isConnected: false,
      reconnectAttempts: 0,
    });
  },
}));
