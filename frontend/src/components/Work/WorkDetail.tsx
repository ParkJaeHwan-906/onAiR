import "../../styles/WorkDetail.css";
import type { Work } from "../../types/work";
import { useUserStore } from "../../store/useUserStore";
import { useWebRtcRequestStore } from "../../store/useWebRtcRequestStore";
import { sendConnectionRequest } from "../../api/webrtc";
import WorkAdd from "./WorkAdd";
import Modal from "./Modal";
import { useState, useEffect } from "react";
import { useSSEStore } from "../../store/useSSEStore";

type WorkDetailProps = {
  work: Work | null;
};

function WorkDetail({ work }: WorkDetailProps) {
  const { myInfo } = useUserStore();
  const { addSentRequest } = useWebRtcRequestStore();
  const isAdmin = myInfo?.role === "관리자";
  const [showRequestBox, setShowRequestBox] = useState(false);
  const { isConnected, connect } = useSSEStore();

  // 요청 기능 사용 전, SSE 연결이 없으면 선연결
  useEffect(() => {
    if (!isConnected) {
      connect();
    }
  }, [isConnected, connect]);

  // 연결 요청 핸들러 (작업자가 관리자에게 요청)
  const handleConnectionRequest = async (_description: string) => {
    if (!work || isAdmin) return; // 관리자는 작업 상세에서 요청하지 않음

    try {
      // 혹시 연결이 끊겨있다면 재연결 시도
      if (!isConnected) connect();

      // 작업자가 요청할 때는 receiverAccountId를 -1로 전송
      const res = await sendConnectionRequest(-1);

      if (!res.success) {
        alert(res.message || "연결 요청 중 오류가 발생했습니다.");
        return;
      }

      // 작업자가 보낸 요청 정보를 sentRequests에 저장
      // 관리자 정보는 회사에서 찾아야 하지만, 일단 null로 저장
      // 나중에 SSE 응답을 받을 때 requests에서 관리자 정보를 찾아서 사용
      if (myInfo) {
        addSentRequest(
          {
            senderAccountId: myInfo.userAccountId,
            name: myInfo.name,
            phone: myInfo.phone || "",
            equipmentName: myInfo.equipmentName || null,
          },
          undefined // 관리자 정보는 나중에 requests에서 찾아서 사용
        );
      }

      alert("연결 요청이 성공적으로 전송되었습니다.");
      setShowRequestBox(false);
      // 요청만 보내고 응답을 기다림 (SSE로 토큰을 받을 예정)
      // 백엔드에서 관리자에게 SSE로 전달되며, 관리자는 HomePage의 요청 목록에서 확인 가능
    } catch (error) {
      console.error("연결 요청 중 오류:", error);
      alert("요청 처리 중 오류가 발생했습니다.");
    }
  };

  if (!work) {
    return (
      <div className="work-detail-wrapper">
        <div className="work-detail-header">작업 상세 정보</div>
        <span className="work-detail-empty">작업을 선택해주세요.</span>
      </div>
    );
  }

  // 시간 포맷팅
  const formatTime = (dateTimeString: string) => {
    if (!dateTimeString) return "-";
    const utcDate = new Date(dateTimeString);
    const kstDate = new Date(utcDate.getTime() + 9 * 60 * 60 * 1000);
    const year = kstDate.getFullYear();
    const month = String(kstDate.getMonth() + 1).padStart(2, "0");
    const day = String(kstDate.getDate()).padStart(2, "0");
    const hours = String(kstDate.getHours()).padStart(2, "0");
    const minutes = String(kstDate.getMinutes()).padStart(2, "0");
    return `${year}-${month}-${day} ${hours}:${minutes}`;
  };

  // 상태 변환
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

  const statusText =
    work.actionStatus && work.actionStatus.trim()
      ? work.actionStatus
      : getActionStatus(work.action);

  return (
    <div className="work-detail-wrapper">
      <div className="work-detail-header">작업 상세 정보</div>

      <dl className="work-detail-list">
        <div className="work-detail-item">
          <dt>작업자</dt>
          <dd>{work.userName || "미할당"}</dd>
        </div>
        <div className="work-detail-item">
          <dt>설비</dt>
          <dd>{work.equipmentName || "미지정"}</dd>
        </div>
        <div className="work-detail-item">
          <dt>작업 내용</dt>
          <dd>{work.request || "-"}</dd>
        </div>
        <div className="work-detail-item">
          <dt>상태</dt>
          <dd>
            <span className="work-detail-status">{statusText}</span>
          </dd>
        </div>
        <div className="work-detail-item">
          <dt>요청 시간</dt>
          <dd>{formatTime(work.lastUpdateTime)}</dd>
        </div>
        {isAdmin && work.solution && (
          <div className="work-detail-item">
            <dt>완료/취소 내용</dt>
            <dd>{work.solution}</dd>
          </div>
        )}
      </dl>

      {/* 작업자가 관리자에게 연결 요청 */}
      {!isAdmin && (
        <>
          <button
            className="work-detail-connect-button"
            onClick={() => setShowRequestBox(true)}
          >
            연결 요청
          </button>

          <Modal
            isOpen={showRequestBox}
            onClose={() => setShowRequestBox(false)}
          >
            <WorkAdd
              title="연결 요청"
              label="요청 사유"
              placeholder="요청 사유를 입력하세요."
              buttonText="연결 요청 보내기"
              onSubmit={(text) => {
                handleConnectionRequest(text);
              }}
            />
          </Modal>
        </>
      )}
    </div>
  );
}

export default WorkDetail;
