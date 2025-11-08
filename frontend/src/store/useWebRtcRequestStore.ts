import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";

export interface WebRtcRequest {
  id: string; // 고유 ID (타임스탬프 + senderAccountId)
  senderAccountId: number;
  name: string;
  phone: string;
  equipmentName: string | null;
  description?: string;
  requestTime: string; // 요청 시간
  status: "pending" | "accepted" | "rejected" | "completed"; // 요청 상태
  accessToken?: string; // 응답 시 받은 토큰
  // 상대방 정보 (요청을 보낼 때 저장)
  receiverInfo?: {
    senderAccountId: number; // 상대방의 accountId
    name: string;
    phone: string;
    equipmentName: string | null;
  };
}

interface WebRtcRequestState {
  requests: WebRtcRequest[];
  sentRequests: WebRtcRequest[]; // 내가 보낸 요청 (응답을 받기 위해 추적)
  requestCount: number; // 오늘의 신규 요청 수

  // 요청 추가 (받은 요청)
  addRequest: (
    request: Omit<WebRtcRequest, "id" | "requestTime" | "status">
  ) => void;

  // 보낸 요청 추가 (응답을 받기 위해 추적)
  addSentRequest: (
    request: Omit<WebRtcRequest, "id" | "requestTime" | "status">,
    receiverInfo?: {
      senderAccountId: number;
      name: string;
      phone: string;
      equipmentName: string | null;
    }
  ) => void;

  // 요청 상태 업데이트 (응답 받았을 때)
  updateRequestStatus: (
    senderAccountId: number,
    acceptConnection: boolean,
    accessToken?: string
  ) => void;

  // 보낸 요청 상태 업데이트 (응답 받았을 때)
  updateSentRequestStatus: (
    acceptConnection: boolean,
    accessToken?: string
  ) => void;

  // 요청 완료 처리 (통신 종료 시)
  completeRequest: (senderAccountId: number) => void;

  // 보낸 요청 완료 처리 (통신 종료 시)
  completeSentRequest: () => void;

  // 오늘의 요청만 필터링
  getTodayRequests: () => WebRtcRequest[];

  // 오늘의 요청 수 계산
  calculateTodayCount: () => void;

  // 요청 초기화 (필요시)
  reset: () => void;
}

export const useWebRtcRequestStore = create<WebRtcRequestState>()(
  persist(
    (set, get) => ({
      requests: [],
      sentRequests: [],
      requestCount: 0,

      addRequest: (requestData) => {
        // 중복 체크: 같은 senderAccountId의 pending 요청이 이미 있으면 추가하지 않음
        const existingRequest = get().requests.find(
          (req) =>
            req.senderAccountId === requestData.senderAccountId &&
            req.status === "pending"
        );

        if (existingRequest) {
          console.log(
            "중복 요청 감지, 추가하지 않음:",
            requestData.senderAccountId
          );
          return;
        }

        const now = new Date();
        const id = `${now.getTime()}_${requestData.senderAccountId}`;
        const requestTime = now.toISOString();

        const newRequest: WebRtcRequest = {
          ...requestData,
          id,
          requestTime,
          status: "pending",
          description: requestData.description ?? "",
        };

        set((state) => {
          const updatedRequests = [...state.requests, newRequest];
          const today = new Date();
          const pendingTodayCount = updatedRequests.filter((req) => {
            const reqDate = new Date(req.requestTime);
            return (
              reqDate.getFullYear() === today.getFullYear() &&
              reqDate.getMonth() === today.getMonth() &&
              reqDate.getDate() === today.getDate() &&
              req.status === "pending"
            );
          }).length;

          return {
            requests: updatedRequests,
            requestCount: pendingTodayCount,
          };
        });
      },

      addSentRequest: (requestData, receiverInfo) => {
        const now = new Date();
        const id = `${now.getTime()}_${requestData.senderAccountId}`;
        const requestTime = now.toISOString();

        const newRequest: WebRtcRequest = {
          ...requestData,
          id,
          requestTime,
          status: "pending",
          description: requestData.description ?? "",
          receiverInfo: receiverInfo || undefined,
        };

        set((state) => ({
          sentRequests: [...state.sentRequests, newRequest],
        }));
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

      updateSentRequestStatus: (acceptConnection, accessToken) => {
        set((state) => ({
          sentRequests: state.sentRequests.map((req) =>
            req.status === "pending"
              ? {
                  ...req,
                  status: (acceptConnection ? "accepted" : "rejected") as
                    | "accepted"
                    | "rejected",
                  accessToken: accessToken || req.accessToken,
                }
              : req
          ),
        }));
        get().calculateTodayCount();
      },

      completeRequest: (senderAccountId) => {
        set((state) => ({
          requests: state.requests.map((req) =>
            req.senderAccountId === senderAccountId &&
            (req.status === "accepted" || req.status === "pending")
              ? { ...req, status: "completed" as "completed" }
              : req
          ),
        }));
        get().calculateTodayCount();
      },

      completeSentRequest: () => {
        set((state) => ({
          sentRequests: state.sentRequests.map((req) =>
            req.status === "accepted" || req.status === "pending"
              ? { ...req, status: "completed" as "completed" }
              : req
          ),
        }));
        get().calculateTodayCount();
      },

      getTodayRequests: () => {
        const today = new Date();
        return get()
          .requests.filter((req) => {
            const reqDate = new Date(req.requestTime);
            return (
              reqDate.getFullYear() === today.getFullYear() &&
              reqDate.getMonth() === today.getMonth() &&
              reqDate.getDate() === today.getDate()
            );
          })
          .sort(
            (a, b) =>
              new Date(b.requestTime).getTime() -
              new Date(a.requestTime).getTime()
          );
      },

      calculateTodayCount: () => {
        const today = new Date();
        const pendingCount = get().requests.filter((req) => {
          const reqDate = new Date(req.requestTime);
          return (
            reqDate.getFullYear() === today.getFullYear() &&
            reqDate.getMonth() === today.getMonth() &&
            reqDate.getDate() === today.getDate() &&
            req.status === "pending"
          );
        }).length;

        set({ requestCount: pendingCount });
      },

      reset: () => {
        set({ requests: [], sentRequests: [], requestCount: 0 });
      },
    }),
    {
      name: "webrtc-request-storage",
      storage: createJSONStorage(() => localStorage),
      // 오늘 날짜가 아닌 요청은 제외
      partialize: (state) => ({
        requests: state.requests.filter((req) => {
          const reqDate = new Date(req.requestTime);
          const today = new Date();
          return (
            reqDate.getFullYear() === today.getFullYear() &&
            reqDate.getMonth() === today.getMonth() &&
            reqDate.getDate() === today.getDate()
          );
        }),
        sentRequests: state.sentRequests.filter((req) => {
          const reqDate = new Date(req.requestTime);
          const today = new Date();
          return (
            reqDate.getFullYear() === today.getFullYear() &&
            reqDate.getMonth() === today.getMonth() &&
            reqDate.getDate() === today.getDate()
          );
        }),
        requestCount: state.requestCount,
      }),
    }
  )
);
