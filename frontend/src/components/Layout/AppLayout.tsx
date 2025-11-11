import { useCallback, useEffect, useRef } from "react";
import { Outlet, useNavigate } from "react-router-dom";
import "../../styles/AppLayout.css";
import SideBar from "../SideBar/SideBar";
import TopBar from "../TopBar/TopBar";
import { useSSEStore } from "../../store/useSSEStore";
import { useUserStore } from "../../store/useUserStore";
import { useWebRtcRequestStore } from "../../store/useWebRtcRequestStore";

function AppLayout() {
  const navigate = useNavigate();
  const { connect, disconnect, eventSource } = useSSEStore();
  const { myInfo, fetchMyInfo } = useUserStore();

  const addRequest = useWebRtcRequestStore((state) => state.addRequest);
  const updateSentRequestStatus = useWebRtcRequestStore(
    (state) => state.updateSentRequestStatus
  );
  const calculateTodayCount = useWebRtcRequestStore(
    (state) => state.calculateTodayCount
  );

  const pendingEventsRef = useRef<any[]>([]);

  useEffect(() => {
    connect();

    return () => {
      disconnect();
    };
  }, [connect, disconnect]);

  // 최초 myInfo 로드
  useEffect(() => {
    fetchMyInfo();
  }, [fetchMyInfo]);

  const processEvent = useCallback(
    (rawData: any) => {
      if (!rawData) return;

      if (!myInfo) {
        pendingEventsRef.current.push(rawData);
        return;
      }

      try {
        const data = rawData;

        const isRequestEvent =
          data.senderAccountId &&
          data.name &&
          data.role &&
          data.acceptConnection === undefined;

        if (isRequestEvent) {
          const isManagerReceivingWorker =
            myInfo.role === "관리자" && data.role === "사용자";
          const isWorkerReceivingManager =
            myInfo.role !== "관리자" && data.role === "관리자";

          if (!isManagerReceivingWorker && !isWorkerReceivingManager) {
            return;
          }

          const { requests } = useWebRtcRequestStore.getState();
          const alreadyExists = requests.some(
            (req) =>
              req.senderAccountId === data.senderAccountId &&
              req.status === "pending"
          );

          if (alreadyExists) {
            return;
          }

          addRequest({
            senderAccountId: data.senderAccountId,
            name: data.name,
            phone: data.phone || "",
            equipmentName: data.equipmentName || null,
            description: data.description ?? "",
          });
          calculateTodayCount();
          return;
        }

        if (typeof data.acceptConnection === "boolean") {
          if (data.acceptConnection && data.accessToken) {
            const { sentRequests, requests } = useWebRtcRequestStore.getState();

            const myPendingRequest = sentRequests
              .filter((req) => req.status === "pending")
              .sort(
                (a, b) =>
                  new Date(b.requestTime).getTime() -
                  new Date(a.requestTime).getTime()
              )[0];

            if (!myPendingRequest) {
              return;
            }

            let partnerInfo = myPendingRequest.receiverInfo;

            if (!partnerInfo) {
              const receivedRequest = requests.find(
                (req) => req.status === "pending"
              );
              if (receivedRequest) {
                partnerInfo = {
                  senderAccountId: receivedRequest.senderAccountId,
                  name: receivedRequest.name,
                  phone: receivedRequest.phone,
                  equipmentName: receivedRequest.equipmentName,
                };
              }
            }

            updateSentRequestStatus(true, data.accessToken);
            calculateTodayCount();

            navigate("/communication", {
              state: {
                token: data.accessToken,
                partnerInfo: partnerInfo || null,
              },
              replace: true,
            });
          } else {
            updateSentRequestStatus(false);
            calculateTodayCount();
          }
        }
      } catch (error) {
        console.error("SSE 이벤트 처리 중 오류", error);
      }
    },
    [addRequest, calculateTodayCount, myInfo, navigate, updateSentRequestStatus]
  );

  useEffect(() => {
    if (!eventSource) return;

    const handleMessage = (event: MessageEvent) => {
      try {
        const data =
          typeof event.data === "string" ? JSON.parse(event.data) : event.data;
        processEvent(data);
      } catch (error) {
        console.error("SSE 데이터 파싱 실패", error);
      }
    };

    const previousHandler = eventSource.onmessage;
    eventSource.onmessage = (event: MessageEvent) => {
      if (previousHandler) previousHandler(event);
      handleMessage(event);
    };

    return () => {
      if (previousHandler) {
        eventSource.onmessage = previousHandler;
      } else {
        eventSource.onmessage = null;
      }
    };
  }, [eventSource, processEvent]);

  useEffect(() => {
    if (!myInfo || pendingEventsRef.current.length === 0) return;

    const queued = [...pendingEventsRef.current];
    pendingEventsRef.current = [];
    queued.forEach((event) => processEvent(event));
  }, [myInfo, processEvent]);

  return (
    <div className="app-layout">
      <SideBar />
      <div className="app-layout-content">
        <TopBar />
        <main className="app-layout-main">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

export default AppLayout;
