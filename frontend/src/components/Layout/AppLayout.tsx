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
  const { eventSource } = useSSEStore();
  const { myInfo, fetchMyInfo } = useUserStore();

  const addRequest = useWebRtcRequestStore((state) => state.addRequest);
  const updateSentRequestStatus = useWebRtcRequestStore(
    (state) => state.updateSentRequestStatus
  );
  const cancelSentRequestByTimeout = useWebRtcRequestStore(
    (state) => state.cancelSentRequestByTimeout
  );
  const cancelRequestByTimeout = useWebRtcRequestStore(
    (state) => state.cancelRequestByTimeout
  );
  const calculateTodayCount = useWebRtcRequestStore(
    (state) => state.calculateTodayCount
  );

  const pendingEventsRef = useRef<any[]>([]);

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

    const dispatchEventPayload = (event: MessageEvent) => {
      try {
        const parsed =
          typeof event.data === "string" ? JSON.parse(event.data) : event.data;

        if (parsed?.type && parsed?.payload) {
          processEvent(parsed.payload);
        } else {
          processEvent(parsed);
        }
      } catch (error) {
        console.error("SSE 데이터 파싱 실패", error);
      }
    };

    const previousHandler = eventSource.onmessage;
    const onMessage = (event: MessageEvent) => {
      if (previousHandler) previousHandler(event);
      dispatchEventPayload(event);
    };

    eventSource.onmessage = onMessage;

    const namedEvents = [
      "taskAssign",
      "taskCancel",
      "taskEnd",
      "callRequest",
      "callResponse",
      "rtcCanceled",
    ];

    const registeredHandlers = namedEvents.map((type) => {
      const handler = (event: MessageEvent) => dispatchEventPayload(event);
      eventSource.addEventListener(type, handler);
      return { type, handler };
    });

    return () => {
      if (previousHandler) {
        eventSource.onmessage = previousHandler;
      } else {
        eventSource.onmessage = null;
      }

      registeredHandlers.forEach(({ type, handler }) => {
        eventSource.removeEventListener(type, handler);
      });
    };
  }, [eventSource, processEvent]);

  useEffect(() => {
    const handleIncomingCall = (event: Event) => {
      const detail = (event as CustomEvent).detail;
      if (!detail) return;
      processEvent(detail);
    };

    const handleCallResponse = (event: Event) => {
      const detail = (event as CustomEvent).detail;
      if (!detail) return;
      processEvent(detail);
    };

    const handleRtcCanceled = (event: Event) => {
      const detail = (event as CustomEvent).detail;
      if (!detail) return;

      // rtcCanceled 이벤트는 시간 초과로 인한 취소
      // console.log("rtcCanceled 이벤트 수신 - 시간 초과로 인한 취소:", detail);

      if (!myInfo) {
        // console.warn("myInfo가 없어 rtcCanceled 이벤트를 처리할 수 없습니다.");
        return;
      }

      // 관리자인 경우: 보낸 요청을 timeout으로 변경
      if (myInfo.role === "관리자") {
        cancelSentRequestByTimeout();
      } else {
        // 작업자인 경우: 받은 요청을 timeout으로 변경
        // detail에서 requestUserAccountId 또는 senderAccountId를 확인
        const senderAccountId =
          detail.requestUserAccountId || detail.senderAccountId;
        if (senderAccountId) {
          cancelRequestByTimeout(senderAccountId);
        }
        // else {
        //   console.warn(
        //     "rtcCanceled 이벤트에 senderAccountId가 없습니다:",
        //     detail
        //   );
        // }
      }
      calculateTodayCount();
    };

    window.addEventListener(
      "incomingCall",
      handleIncomingCall as EventListener
    );
    window.addEventListener(
      "callResponse",
      handleCallResponse as EventListener
    );
    window.addEventListener("rtcCanceled", handleRtcCanceled as EventListener);

    return () => {
      window.removeEventListener(
        "incomingCall",
        handleIncomingCall as EventListener
      );
      window.removeEventListener(
        "callResponse",
        handleCallResponse as EventListener
      );
      window.removeEventListener(
        "rtcCanceled",
        handleRtcCanceled as EventListener
      );
    };
  }, [
    processEvent,
    cancelSentRequestByTimeout,
    cancelRequestByTimeout,
    calculateTodayCount,
    myInfo,
  ]);

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
