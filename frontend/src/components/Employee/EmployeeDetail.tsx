import "../../styles/EmployeeDetail.css";
import type { Employee } from "../../types/employee";
import { useUserStore } from "../../store/useUserStore";
import { formatPhone } from "../../utils/formatPhone";
import { sendConnectionRequest, getLivekitToken } from "../../api/webrtc";
import { useNavigate } from "react-router-dom";
import WorkAdd from "../Work/WorkAdd";
import Modal from "../Work/Modal";
import { useState, useEffect } from "react";
import { useSSEStore } from "../../store/useSSEStore";

type EmployeeDetailProps = {
  employee: Employee | null;
};

function EmployeeDetail({ employee }: EmployeeDetailProps) {
  const { myInfo } = useUserStore();
  const isMine = myInfo?.userAccountId === employee?.userAccountId;
  const isAdmin = myInfo?.role === "관리자";
  const navigate = useNavigate();
  const [showRequestBox, setShowRequestBox] = useState(false);
  const { isConnected, connect } = useSSEStore();

  // 요청 기능 사용 전, SSE 연결이 없으면 선연결
  useEffect(() => {
    if (!isConnected) {
      connect();
    }
  }, [isConnected, connect]);

  // description(요청 사유) 받도록 수정
  const handleConnectionRequest = async (description: string) => {
    if (!employee || !isAdmin) return;

    try {
      // 혹시 연결이 끊겨있다면 재연결 시도
      if (!isConnected) connect();

      const receiverId = employee.userAccountId;
      console.log("보내는 receiverAccountId:", receiverId);
      console.log("요청 사유:", description);

      // 연결 요청 시 description도 함께 전달
      const res = await sendConnectionRequest(receiverId, description);

      if (!res.success) {
        alert(res.message || "연결 요청 중 오류가 발생했습니다.");
        return;
      }

      alert("연결 요청이 성공적으로 전송되었습니다.");

      // LiveKit 토큰 발급
      const roomName = `room-${receiverId}`;
      const token = await getLivekitToken(roomName);

      if (token) {
        console.log("LiveKit 토큰:", token);
        navigate("/communication", { state: { token, roomName } });
      } else {
        alert("LiveKit 토큰 발급 실패");
      }
    } catch (error) {
      console.error("연결 요청 중 오류:", error);
      alert("요청 처리 중 오류가 발생했습니다.");
    }
  };

  if (!employee) {
    return (
      <div className="detail-wrapper">
        <div className="detail-header">직원 상세 정보</div>
        <span className="detail-empty">직원을 선택해주세요.</span>
      </div>
    );
  }

  return (
    <div className="detail-wrapper">
      <div className="detail-header">직원 상세 정보</div>

      <div className="profile-section">
        <img
          src={"images/default-profile.png"}
          alt="프로필"
          className="profile-img"
        />
        <h2 className="detail-title">{employee.name}</h2>
        <p className="detail-email">{employee.email}</p>
      </div>

      <dl className="detail-list">
        <div className="detail-item">
          <dt>부서</dt>
          <dd>{employee.part || "미등록"}</dd>
        </div>
        <div className="detail-item">
          <dt>연락처</dt>
          <dd>{formatPhone(employee.phone)}</dd>
        </div>

        {isAdmin && (
          <div className="detail-item">
            <dt>담당 설비</dt>
            <dd>{employee.equipmentName || "미지정"}</dd>
          </div>
        )}

        {!isAdmin && isMine && (
          <>
            <div className="detail-item">
              <dt>회사</dt>
              <dd>{employee.company}</dd>
            </div>
            <div className="detail-item">
              <dt>생년월일</dt>
              <dd>{employee.birth || "등록되지 않음"}</dd>
            </div>
          </>
        )}

        <div className="detail-item">
          <dt>근무 상태</dt>
          <dd>
            <span
              className="detail-status"
              data-online={employee.online ? "true" : "false"}
            >
              {employee.online ? "온라인" : "오프라인"}
            </span>
          </dd>
        </div>
      </dl>

      {/* 모달로 변경 */}
      {isAdmin && (
        <>
          <button
            className="connect-button"
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
                setShowRequestBox(false);
              }}
            />
          </Modal>
        </>
      )}

      {!isAdmin && <button className="connect-button">정보 수정</button>}
    </div>
  );
}

export default EmployeeDetail;
