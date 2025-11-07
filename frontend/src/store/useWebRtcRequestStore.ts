import { create } from "zustand";

export interface WebRtcRequest {
  id: string; // 고유 ID (타임스탬프 + senderAccountId)
  senderAccountId: number;
  name: string;
  phone: string;
  equipmentName: string | null;
  requestTime: string; // 요청 시간
  status: "pending" | "accepted" | "rejected"; // 요청 상태
  accessToken?: string; // 응답 시 받은 토큰
}

interface WebRtcRequestState {
  requests: WebRtcRequest[];
  requestCount: number; // 오늘의 신규 요청 수

  // 요청 추가
  addRequest: (request: Omit<WebRtcRequest, "id" | "requestTime" | "status">) => void;
  
  // 요청 상태 업데이트 (응답 받았을 때)
  updateRequestStatus: (senderAccountId: number, acceptConnection: boolean, accessToken?: string) => void;
  
  // 오늘의 요청만 필터링
  getTodayRequests: () => WebRtcRequest[];
  
  // 오늘의 요청 수 계산
  calculateTodayCount: () => void;
  
  // 요청 초기화 (필요시)
  reset: () => void;
}

export const useWebRtcRequestStore = create<WebRtcRequestState>((set, get) => ({
  requests: [],
  requestCount: 0,

  addRequest: (requestData) => {
    const now = new Date();
    const id = `${now.getTime()}_${requestData.senderAccountId}`;
    const requestTime = now.toISOString();
    
    const newRequest: WebRtcRequest = {
      ...requestData,
      id,
      requestTime,
      status: "pending",
    };

    set((state) => {
      const updatedRequests = [...state.requests, newRequest];
      return {
        requests: updatedRequests,
        requestCount: updatedRequests.filter((req) => {
          const reqDate = new Date(req.requestTime);
          const today = new Date();
          return (
            reqDate.getFullYear() === today.getFullYear() &&
            reqDate.getMonth() === today.getMonth() &&
            reqDate.getDate() === today.getDate()
          );
        }).length,
      };
    });
  },

  updateRequestStatus: (senderAccountId, acceptConnection, accessToken) => {
    set((state) => ({
      requests: state.requests.map((req) =>
        req.senderAccountId === senderAccountId && req.status === "pending"
          ? {
              ...req,
              status: acceptConnection ? "accepted" : "rejected",
              accessToken: accessToken || req.accessToken,
            }
          : req
      ),
    }));
    get().calculateTodayCount();
  },

  getTodayRequests: () => {
    const today = new Date();
    return get().requests.filter((req) => {
      const reqDate = new Date(req.requestTime);
      return (
        reqDate.getFullYear() === today.getFullYear() &&
        reqDate.getMonth() === today.getMonth() &&
        reqDate.getDate() === today.getDate()
      );
    });
  },

  calculateTodayCount: () => {
    const todayRequests = get().getTodayRequests();
    set({ requestCount: todayRequests.length });
  },

  reset: () => {
    set({ requests: [], requestCount: 0 });
  },
}));

