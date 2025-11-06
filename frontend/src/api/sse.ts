import { EventSourcePolyfill } from "event-source-polyfill";
import { api } from "./axiosInstance";

// SSE 연결 함수
export const connectSSE = (onMessage: (event: MessageEvent) => void) => {
  const token = localStorage.getItem("accessToken");

  if (!token) {
    console.error("토큰이 존재하지 않습니다. SSE 연결 불가");
    return null;
  }

  // sse 객체 생성
  const eventSource = new EventSourcePolyfill(
    `${api.defaults.baseURL}/sse/stream`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
      heartbeatTimeout: 60000, // 1분마다 연결 유지 ping
    }
  );

  // 연결 성공
  eventSource.onopen = () => {
    console.log("SSE 연결 성공");
  };

  // 서버 이벤트 수신
  eventSource.onmessage = (event: MessageEvent) => {
    console.log("SSE 이벤트 수신:", event.data);
    onMessage(event);
  };

  // 오류 발생 시
  eventSource.onerror = (error: any) => {
    console.error("SSE 연결 오류:", error);
    eventSource.close();
  };

  return eventSource;
};

// SSE 연결 종료 함수
export const disconnectSSE = (eventSource: any) => {
  if (eventSource) {
    eventSource.close();
    console.log("SSE 연결 종료");
  }
};
