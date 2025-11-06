import { EventSourcePolyfill } from "event-source-polyfill";
import { api } from "./axiosInstance";

// 재연결 설정
const MAX_RECONNECT_ATTEMPTS = 10; // 최대 재연결 시도 횟수
const INITIAL_RECONNECT_DELAY = 1000; // 초기 재연결 지연 시간 (1초)
const MAX_RECONNECT_DELAY = 30000; // 최대 재연결 지연 시간 (30초)

// SSE 연결 함수 (재연결 로직 포함)
export const connectSSE = (
  onMessage: (event: MessageEvent) => void,
  onReconnect?: (attempt: number) => void,
  onError?: (error: any) => void
) => {
  const token = localStorage.getItem("accessToken");

  if (!token) {
    return null;
  }

  let reconnectAttempts = 0;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let eventSource: any | null = null;
  let isManualClose = false; // 수동 종료 여부

  const connect = (): any | null => {
    // 이미 연결되어 있으면 재연결하지 않음
    if (eventSource && eventSource.readyState !== EventSource.CLOSED && !isManualClose) {
      return eventSource;
    }

    // 이전 연결이 있으면 정리
    if (eventSource) {
      try {
        eventSource.close();
      } catch (e) {
        // 이미 닫혀있을 수 있음
      }
    }

    // 최대 재연결 시도 횟수 초과
    if (reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
      if (onError) {
        onError(new Error("SSE 재연결 실패: 최대 시도 횟수 초과"));
      }
      return null;
    }

    // sse 객체 생성
    const sseUrl = `${api.defaults.baseURL}/sse/stream`;
    console.log("🔌 SSE 연결 시도:", sseUrl);
    console.log("🔑 토큰 존재:", !!token);
    
    eventSource = new EventSourcePolyfill(
      sseUrl,
      {
        headers: {
          Authorization: `Bearer ${token}`,
        },
        heartbeatTimeout: 60000, // 1분마다 연결 유지 ping
      }
    );
    
    console.log("📡 EventSourcePolyfill 생성 완료 - readyState:", eventSource.readyState);

    // 연결 성공
    eventSource.onopen = () => {
      console.log("✅ SSE 연결 성공 (onopen)");
      reconnectAttempts = 0; // 재연결 성공 시 카운터 리셋
      
      // 재연결 타이머가 있으면 정리
      if (reconnectTimer) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }
    };

    // 서버 이벤트 수신
    eventSource.onmessage = (event: MessageEvent) => {
      console.log("📨 SSE 메시지 수신:", event.data);
      onMessage(event);
    };

    // 특정 이벤트 타입별 처리 (ping 이벤트 등)
    eventSource.addEventListener("ping", () => {
      console.log("🏓 SSE ping 이벤트 수신 - 연결 유지");
      // ping 이벤트 수신 시 연결 유지 (타임아웃 리셋)
      // heartbeatTimeout이 자동으로 처리하지만 명시적으로 처리
    });

    eventSource.addEventListener("connect", (event: any) => {
      console.log("🔗 SSE connect 이벤트 수신:", event.data);
      // 연결 성공 이벤트
      onMessage(event);
    });

    // 오류 발생 시
    eventSource.onerror = () => {
      const readyState = eventSource?.readyState;
      console.error("❌ SSE 연결 오류 - readyState:", readyState, {
        CONNECTING: EventSource.CONNECTING,
        OPEN: EventSource.OPEN,
        CLOSED: EventSource.CLOSED
      });

      // 수동으로 닫은 경우가 아니고, 연결이 끊어진 경우에만 재연결 시도
      if (!isManualClose && readyState === EventSource.CLOSED) {
        reconnectAttempts++;
        console.log(`🔄 SSE 재연결 시도 ${reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS}`);
        
        // 지수 백오프: 재연결 지연 시간 계산 (1초, 2초, 4초, 8초, ... 최대 30초)
        const delay = Math.min(
          INITIAL_RECONNECT_DELAY * Math.pow(2, reconnectAttempts - 1),
          MAX_RECONNECT_DELAY
        );
        
        console.log(`⏳ ${delay}ms 후 재연결 시도...`);
        
        if (onReconnect) {
          onReconnect(reconnectAttempts);
        }

        // 재연결 시도
        reconnectTimer = setTimeout(() => {
          if (!isManualClose) {
            console.log("🔄 재연결 시작...");
            connect();
          }
        }, delay);
      }
    };

    return eventSource;
  };

  // 초기 연결
  const initialEventSource = connect();

  // 종료 함수를 이벤트 소스에 추가
  if (initialEventSource) {
    (initialEventSource as any).manualClose = () => {
      isManualClose = true;
      if (reconnectTimer) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }
      if (initialEventSource) {
        initialEventSource.close();
      }
    };
  }

  return initialEventSource;
};

// SSE 연결 종료 함수
export const disconnectSSE = (eventSource: any) => {
  if (eventSource) {
    // 수동 종료 플래그 설정 (재연결 방지)
    if (eventSource.manualClose) {
      eventSource.manualClose();
    } else {
      eventSource.close();
    }
  }
};
