import { EventSourcePolyfill } from "event-source-polyfill";
import { api } from "./axiosInstance";

// 재연결 설정
const MAX_RECONNECT_ATTEMPTS = 10;
const INITIAL_RECONNECT_DELAY = 1000;
const MAX_RECONNECT_DELAY = 30000;

// SSE 연결 함수 (재연결 로직 포함)
export const connectSSE = (
  onMessage: (event: MessageEvent) => void,
  onReconnect?: (attempt: number) => void,
  onError?: (error: any) => void
) => {
  const token = localStorage.getItem("accessToken");
  if (!token) return null;

  let reconnectAttempts = 0;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let eventSource: any | null = null;
  let isManualClose = false;

  const connect = (): any | null => {
    if (
      eventSource &&
      eventSource.readyState !== EventSource.CLOSED &&
      !isManualClose
    ) {
      return eventSource;
    }

    if (eventSource) {
      try {
        eventSource.close();
      } catch {}
    }

    if (reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
      onError?.(new Error("SSE 재연결 실패: 최대 시도 횟수 초과"));
      return null;
    }

    const sseUrl = `${api.defaults.baseURL}/sse/stream`;
    console.log("SSE 연결 시도 중... (토큰 존재:", !!token, ")");

    eventSource = new EventSourcePolyfill(sseUrl, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
      heartbeatTimeout: 60000,
    });

    // 연결 성공
    eventSource.onopen = () => {
      console.log("SSE 연결 성공 (onopen)");
      reconnectAttempts = 0;
      if (reconnectTimer) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }
    };

    // event: 가 있는 커스텀 이벤트 타입 자동 등록
    const eventNames = [
      "connect",
      "heart beat",
      "taskAssign",
      "taskCancel",
      "taskEnd",
      "callRequest",
      "callResponse",
      "rtcCanceled",
    ];

    eventNames.forEach((name) => {
      eventSource.addEventListener(name, (event: MessageEvent) => {
        console.log(`SSE 이벤트 수신 [${name}]:`, event.data);
        try {
          // heart beat 이벤트는 JSON이 아닐 수 있으므로 특별 처리
          if (name === "heart beat" || name === "connect") {
            // 텍스트 형태의 heartbeat 메시지 처리
            handleParsedEvent({ type: name, payload: event.data }, name);
          } else {
            // 다른 이벤트는 JSON 파싱 시도
            const parsed = JSON.parse(event.data);
            handleParsedEvent(parsed, name);
          }
        } catch (err) {
          // JSON 파싱 실패 시 (heart beat가 아닌 경우에만 에러 로그)
          if (name !== "heart beat") {
            console.error(`JSON Parse 실패 (${name})`, event.data, err);
          }
          // 파싱 실패해도 기본 처리 시도
          handleParsedEvent({ type: name, payload: event.data }, name);
        }
        onMessage(event);
      });
    });

    // event: 없는 기본 메시지 처리
    eventSource.onmessage = (event: MessageEvent) => {
      console.log("SSE 기본 메시지 수신:", event.data);

      try {
        const parsed = JSON.parse(event.data);
        handleParsedEvent(parsed, parsed.type || "message");
      } catch {
        handleParsedEvent({ type: "message", payload: event.data }, "message");
      }
      onMessage(event);
    };

    // 오류 및 재연결 처리
    eventSource.onerror = (error: any) => {
      const readyState = eventSource?.readyState;
      console.error("SSE 연결 오류 - readyState:", readyState, error);

      if (
        !isManualClose &&
        (readyState === EventSource.CLOSED ||
          readyState === EventSource.CONNECTING)
      ) {
        reconnectAttempts++;
        const delay = Math.min(
          INITIAL_RECONNECT_DELAY * Math.pow(2, reconnectAttempts - 1),
          MAX_RECONNECT_DELAY
        );
        console.warn(`재연결 시도 ${reconnectAttempts}회 (delay ${delay}ms)`);

        onReconnect?.(reconnectAttempts);
        reconnectTimer = setTimeout(() => {
          if (!isManualClose) connect();
        }, delay);
      }
    };

    return eventSource;
  };

  // 이벤트 데이터 공통 처리 함수
  const handleParsedEvent = (parsed: any, eventName: string) => {
    const type = parsed?.type || eventName;
    const payload = parsed?.payload ?? parsed;

    switch (type) {
      case "connect":
        console.log("연결 유지 확인");
        break;

      case "heart beat":
        console.log("Heartbeat 이벤트 수신:", payload || parsed);
        break;

      case "taskAssign":
        console.log("작업 할당:", payload);
        window.dispatchEvent(new CustomEvent("refreshTasks"));
        break;

      case "taskCancel":
        console.log("작업 취소:", payload);
        window.dispatchEvent(new CustomEvent("refreshTasks"));
        break;

      case "taskEnd":
        console.log("작업 완료:", payload);
        window.dispatchEvent(new CustomEvent("refreshTasks"));
        break;

      case "callRequest":
        console.log("연결 요청:", payload);
        window.dispatchEvent(
          new CustomEvent("incomingCall", { detail: payload })
        );
        break;

      case "callResponse":
        console.log("연결 응답:", payload);
        window.dispatchEvent(
          new CustomEvent("callResponse", { detail: payload })
        );
        break;

      case "rtcCanceled":
        console.log("통신 취소 이벤트 수신:", payload);
        window.dispatchEvent(
          new CustomEvent("rtcCanceled", { detail: payload })
        );
        break;

      default:
        console.log("기타 이벤트 수신:", type, payload);
        break;
    }
  };

  // 초기 연결 시도
  const initialEventSource = connect();

  // 수동 종료 함수 추가
  if (initialEventSource) {
    (initialEventSource as any).manualClose = () => {
      isManualClose = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      initialEventSource.close();
    };
  }

  return initialEventSource;
};

// SSE 연결 종료 함수
export const disconnectSSE = (eventSource: any) => {
  if (eventSource) {
    if (eventSource.manualClose) {
      eventSource.manualClose();
    } else {
      eventSource.close();
    }
  }
};
