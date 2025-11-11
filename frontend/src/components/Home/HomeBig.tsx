import { useMemo } from "react";
import "../../styles/HomeBig.css";
import "../../styles/WorkList.css";
import { useWebRtcRequestStore } from "../../store/useWebRtcRequestStore";
import { sendConnectionResponse } from "../../api/webrtc";
import { useNavigate } from "react-router-dom";
import type { Work } from "../../types/work";

const backColors = ["#F4C0C0", "#F9E9B5", "#B5BFE0", "#B6E7C8"];
const fontColors = ["#EF4444", "#FFBC11", "#1E40AF", "#22C55E"];

type HomeBigProps = {
  title: string;
  icon: string;
  tasks?: Work[];
  formatTime?: (time: string) => string;
  isRequestList?: boolean;
};

function HomeBig({
  title,
  icon,
  tasks = [],
  formatTime,
  isRequestList = false,
}: HomeBigProps) {
  const navigate = useNavigate();

  // Zustand store 구독 - requests만 구독하여 리렌더링 트리거
  const allRequests = useWebRtcRequestStore((state) => state.requests);
  const { updateRequestStatus } = useWebRtcRequestStore();

  // 요청 목록 필터링 및 정렬 (내림차순)
  const requests = useMemo(() => {
    if (!isRequestList) return [];

    const today = new Date();
    const filtered = allRequests.filter((req) => {
      const reqDate = new Date(req.requestTime);
      const isToday =
        reqDate.getFullYear() === today.getFullYear() &&
        reqDate.getMonth() === today.getMonth() &&
        reqDate.getDate() === today.getDate();
      return isToday;
    });

    // 요청시간 기준 내림차순 정렬
    return filtered.sort((a, b) => {
      const timeA = new Date(a.requestTime).getTime();
      const timeB = new Date(b.requestTime).getTime();
      return timeB - timeA; // 내림차순 (최신순부터)
    });
  }, [isRequestList, allRequests]);

  // 작업 목록 정렬 (오름차순)
  const sortedTasks = useMemo(() => {
    if (!tasks || tasks.length === 0) return [];

    return [...tasks].sort((a, b) => {
      const timeA = new Date(a.lastUpdateTime).getTime();
      const timeB = new Date(b.lastUpdateTime).getTime();
      return timeA - timeB; // 오름차순 (오래된 것부터)
    });
  }, [tasks]);

  // 연결 요청 수락/거절 핸들러
  const handleResponse = async (
    senderAccountId: number,
    senderName: string,
    acceptConnection: boolean
  ) => {
    // 유효성 검사
    if (!senderAccountId || !senderName) {
      console.error("유효하지 않은 요청 데이터:", {
        senderAccountId,
        senderName,
      });
      alert("요청 정보가 올바르지 않습니다.");
      return;
    }

    try {
      const res = await sendConnectionResponse(
        senderAccountId,
        senderName,
        acceptConnection
      );

      if (!res.success) {
        alert(res.message || "응답 처리 중 오류가 발생했습니다.");
        return;
      }

      // 수락한 경우에만 토큰을 받고 CommunicationPage로 이동
      if (acceptConnection && res.data?.accessToken) {
        updateRequestStatus(senderAccountId, true, res.data.accessToken);

        // 요청 목록에서 상대방 정보 찾기
        const requests = useWebRtcRequestStore.getState().requests;
        const request = requests.find(
          (req) => req.senderAccountId === senderAccountId
        );

        navigate("/communication", {
          state: {
            token: res.data.accessToken,
            partnerInfo: request
              ? {
                  senderAccountId: request.senderAccountId,
                  name: request.name,
                  phone: request.phone,
                  equipmentName: request.equipmentName,
                }
              : null,
          },
        });
      } else {
        // 거절한 경우 상태만 업데이트
        updateRequestStatus(senderAccountId, false);
        alert(
          acceptConnection
            ? "연결 요청이 수락되었습니다."
            : "연결 요청이 거절되었습니다."
        );
      }
    } catch (error) {
      console.error("연결 응답 중 오류:", error);
      alert("응답 처리 중 오류가 발생했습니다.");
    }
  };

  // action 값을 actionStatus 문자열로 변환
  const getActionStatus = (action: number): string => {
    switch (action) {
      case 0:
        return "취소됨";
      case 1:
        return "대기중";
      case 2:
        return "작업중";
      case 3:
        return "완료";
      default:
        return "대기중";
    }
  };

  // 요청 상태를 한글로 변환
  const getRequestStatus = (status: string): string => {
    switch (status) {
      case "pending":
        return "대기중";
      case "accepted":
        return "수락";
      case "rejected":
        return "거절";
      case "completed":
        return "완료";
      default:
        return "대기중";
    }
  };

  // 요청 상태 색상
  const getRequestStatusColor = (status: string) => {
    switch (status) {
      case "pending":
        return { bg: "#F9E9B5", color: "#FFBC11" };
      case "accepted":
        return { bg: "#B6E7C8", color: "#22C55E" };
      case "rejected":
        return { bg: "#F4C0C0", color: "#EF4444" };
      case "completed":
        return { bg: "#E0E7FF", color: "#6366F1" };
      default:
        return { bg: "#F9E9B5", color: "#FFBC11" };
    }
  };

  // 요청 시간 포맷팅
  const formatRequestTime = (timeString: string) => {
    if (!timeString) return "-";
    const date = new Date(timeString);
    const hours = String(date.getHours()).padStart(2, "0");
    const minutes = String(date.getMinutes()).padStart(2, "0");
    return `${hours}:${minutes}`;
  };

  return (
    <div className="home-big">
      <div className="home-big-header">
        <span className="title">{title}</span>
        <img src={icon} alt="list" />
      </div>
      <div className={`home-table ${isRequestList ? "request-list" : ""}`}>
        <div className="list-header">
          {isRequestList ? (
            <>
              <div className="col-worker">요청자</div>
              <div className="col-content">설비</div>
              <div className="col-description">요청 내용</div>
              <div className="col-status">상태</div>
              <div className="col-time">요청시간</div>
              <div className="col-actions-header">응답</div>
            </>
          ) : (
            <>
              <div className="col-worker">작업자</div>
              <div className="col-content">작업 내용</div>
              <div className="col-status">상태</div>
              <div className="col-time">시간</div>
            </>
          )}
        </div>
        <div className="list-body">
          {isRequestList ? (
            requests.length === 0 ? (
              <p className="no-data">오늘의 요청이 없습니다.</p>
            ) : (
              requests.map((request) => {
                const statusColor = getRequestStatusColor(request.status);
                const isPending = request.status === "pending";
                return (
                  <div key={request.id} className="work-row">
                    <div className="col-worker">{request.name}</div>
                    <div className="col-content">
                      {request.equipmentName || "-"}
                    </div>
                    <div className="col-description">
                      {request.description && request.description.trim()
                        ? request.description
                        : "-"}
                    </div>
                    <div className="col-status">
                      <span
                        className="status-badge"
                        style={{
                          backgroundColor: statusColor.bg,
                          color: statusColor.color,
                        }}
                      >
                        {getRequestStatus(request.status)}
                      </span>
                    </div>
                    <div className="col-time">
                      {formatRequestTime(request.requestTime)}
                    </div>
                    <div className="col-actions">
                      {isPending ? (
                        <>
                          <button
                            className="action-button accept-button"
                            onClick={() =>
                              handleResponse(
                                request.senderAccountId,
                                request.name,
                                true
                              )
                            }
                          >
                            수락
                          </button>
                          <button
                            className="action-button reject-button"
                            onClick={() =>
                              handleResponse(
                                request.senderAccountId,
                                request.name,
                                false
                              )
                            }
                          >
                            거절
                          </button>
                        </>
                      ) : (
                        <span className="no-action">-</span>
                      )}
                    </div>
                  </div>
                );
              })
            )
          ) : sortedTasks.length === 0 ? (
            <p className="no-data">오늘의 작업이 없습니다.</p>
          ) : (
            sortedTasks.map((task) => {
              const actionStatus =
                task.actionStatus && task.actionStatus.trim()
                  ? task.actionStatus
                  : getActionStatus(task.action);
              const formattedTime = formatTime
                ? formatTime(task.lastUpdateTime)
                : task.lastUpdateTime;

              return (
                <div key={task.id} className="work-row">
                  <div className="col-worker">{task.userName || "미할당"}</div>
                  <div className="col-content">{task.request}</div>
                  <div className="col-status">
                    <span
                      className="status-badge"
                      style={{
                        backgroundColor:
                          backColors[
                            task.action >= 0 && task.action < backColors.length
                              ? task.action
                              : 0
                          ],
                        color:
                          fontColors[
                            task.action >= 0 && task.action < fontColors.length
                              ? task.action
                              : 0
                          ],
                      }}
                    >
                      {actionStatus}
                    </span>
                  </div>
                  <div className="col-time">{formattedTime}</div>
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}

export default HomeBig;
