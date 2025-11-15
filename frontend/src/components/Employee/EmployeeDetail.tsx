import "../../styles/EmployeeDetail.css";
import type { Employee } from "../../types/employee";
import { useUserStore } from "../../store/useUserStore";
import { formatPhone } from "../../utils/formatPhone";
import { sendConnectionRequest } from "../../api/webrtc";
import { useWebRtcRequestStore } from "../../store/useWebRtcRequestStore";
import WorkAdd from "../Work/WorkAdd";
import Modal from "../Work/Modal";
import { useState, useEffect, useRef, useMemo } from "react";
import { useSSEStore } from "../../store/useSSEStore";
import { useSSEEventsStore } from "../../store/useSSEEventsStore";
import { getCompanyEquipmentList } from "../../api/equipment";
import { assignEquipment, checkIn, checkOut } from "../../api/user";
import type { Equipment } from "../../types/equipment";

type EmployeeDetailProps = {
  employee: Employee | null;
};

type ModalType = "pending" | "rejected" | "timeout" | "requestBox" | null;

function EmployeeDetail({ employee }: EmployeeDetailProps) {
  const { myInfo, fetchEmployees, fetchMyInfo } = useUserStore();
  const { addSentRequest, sentRequests } = useWebRtcRequestStore();
  const { clearEvents } = useSSEEventsStore();
  const { isConnected, connect } = useSSEStore();

  const isMine = myInfo?.userAccountId === employee?.userAccountId;
  const isAdmin = myInfo?.role === "관리자";

  const [modalType, setModalType] = useState<ModalType>(null);
  const [currentRequestDescription, setCurrentRequestDescription] =
    useState("");
  const [pendingElapsed, setPendingElapsed] = useState(0);
  const [hasDismissedPending, setHasDismissedPending] = useState(false);
  const pendingStartRef = useRef<number | null>(null);

  const [equipments, setEquipments] = useState<Equipment[]>([]);
  const [selectedEquipmentId, setSelectedEquipmentId] = useState<number | null>(
    null
  );
  const [isEquipmentDropdownOpen, setIsEquipmentDropdownOpen] = useState(false);
  const equipmentDropdownRef = useRef<HTMLDivElement | null>(null);
  const [isAssigning, setIsAssigning] = useState(false);
  const [isCheckingInOut, setIsCheckingInOut] = useState(false);

  // -----------------------
  // activeRequest 계산
  // -----------------------
  const activeRequest = useMemo(() => {
    if (!isAdmin || !employee) return null;

    const related = sentRequests.filter(
      (r) => r.receiverInfo?.senderAccountId === employee.userAccountId
    );

    if (related.length === 0) return null;

    return related.sort(
      (a, b) =>
        new Date(b.requestTime).getTime() - new Date(a.requestTime).getTime()
    )[0];
  }, [isAdmin, employee, sentRequests]);

  const isPending = activeRequest?.status === "pending";

  const pendingWorkerName =
    activeRequest?.receiverInfo?.name || employee?.name || "";

  const pendingEquipmentName =
    activeRequest?.receiverInfo?.equipmentName || employee?.equipmentName;

  // -----------------------
  // SSE 이벤트 → 모달 표시
  // -----------------------
  useEffect(() => {
    if (!isAdmin) return;

    const handleRejected = (e: any) => {
      console.log("거절 이벤트:", e.detail);
      setModalType("rejected");
    };

    const handleTimeout = (e: any) => {
      console.log("타임아웃 이벤트:", e.detail);
      setModalType("timeout");
    };

    window.addEventListener("callResponse", handleRejected);
    window.addEventListener("rtcCanceled", handleTimeout);

    return () => {
      window.removeEventListener("callResponse", handleRejected);
      window.removeEventListener("rtcCanceled", handleTimeout);
    };
  }, [isAdmin]);

  // -----------------------
  // pending 자동 오픈
  // -----------------------
  useEffect(() => {
    if (!isAdmin) return;

    // 요청 입력 모달은 무시
    if (modalType === "requestBox") return;

    // 이미 거절/타임아웃 모달 떠 있으면 자동 변경 금지
    if (modalType === "rejected" || modalType === "timeout") return;

    if (isPending && activeRequest) {
      pendingStartRef.current = new Date(activeRequest.requestTime).getTime();
      setCurrentRequestDescription(activeRequest.description ?? "");

      if (!hasDismissedPending) {
        setModalType("pending");
      }
      return;
    }

    setModalType(null);
  }, [isAdmin, modalType, isPending, activeRequest, hasDismissedPending]);

  // -----------------------
  // pending 경과 시간 계산
  // -----------------------
  useEffect(() => {
    if (!isPending) return;
    const start = pendingStartRef.current;
    if (!start) return;

    const tick = () => {
      setPendingElapsed(Math.floor((Date.now() - start) / 1000));
    };
    tick();

    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [isPending]);

  const formatElapsedTime = (sec: number) => {
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  };

  // -----------------------
  // SSE 자동 연결
  // -----------------------
  useEffect(() => {
    if (!isConnected) connect();
  }, [isConnected, connect]);

  // -----------------------
  // 설비 목록 로드
  // -----------------------
  useEffect(() => {
    if (isAdmin && employee) {
      loadEquipments();
      setSelectedEquipmentId(employee.equipmentId || null);
    }
  }, [isAdmin, employee]);

  const loadEquipments = async () => {
    try {
      const res = await getCompanyEquipmentList();
      if (res.success && res.data) {
        setEquipments(res.data);
      }
    } catch (e) {
      console.error("설비 목록 조회 실패:", e);
    }
  };

  // -----------------------
  // 연결 요청 보내기
  // -----------------------
  const handleConnectionRequest = async (description: string) => {
    if (!employee || !isAdmin) return;

    try {
      if (!isConnected) connect();

      const res = await sendConnectionRequest(employee.userAccountId);

      if (!res.success) {
        alert("연결 요청 실패\n작업자 SSE 연결 상태 확인 필요");
        return;
      }

      if (myInfo && employee) {
        addSentRequest(
          {
            senderAccountId: myInfo.userAccountId,
            name: myInfo.name,
            phone: myInfo.phone || "",
            equipmentName: myInfo.equipmentName || null,
            description,
          },
          {
            senderAccountId: employee.userAccountId,
            name: employee.name,
            phone: employee.phone || "",
            equipmentName: employee.equipmentName || null,
          }
        );
      }

      setCurrentRequestDescription(description);
      pendingStartRef.current = Date.now();
      setPendingElapsed(0);
      setHasDismissedPending(false);
      setModalType("pending");
    } catch (e) {
      alert("요청 중 오류 발생");
    }
  };

  // -----------------------
  // 모달 닫기 함수들
  // -----------------------
  const closePending = () => {
    setHasDismissedPending(true);
    clearEvents();
    setModalType(null);
  };

  const closeRejected = () => {
    clearEvents();
    setModalType(null);
  };

  // -----------------------
  // 렌더링 시작
  // -----------------------
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

      {/* 프로필 */}
      <div className="profile-section">
        <img src={"images/default-profile.png"} className="profile-img" />
        <h2 className="detail-title">{employee.name}</h2>
        <p className="detail-email">{employee.email}</p>
      </div>

      {/* 정보 리스트 */}
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
          <>
            <div className="detail-item">
              <dt>담당 설비</dt>
              <dd>{employee.equipmentName || "미지정"}</dd>
            </div>

            <div className="detail-item">
              <dt>설비 지정</dt>
              <dd>
                <div className="equipment-assign-row">
                  <div
                    className="equipment-assign-wrapper"
                    ref={equipmentDropdownRef}
                  >
                    <button
                      className={`equipment-select-trigger ${
                        isEquipmentDropdownOpen ? "open" : ""
                      }`}
                      onClick={() =>
                        setIsEquipmentDropdownOpen((prev) => !prev)
                      }
                      disabled={isAssigning}
                    >
                      {selectedEquipmentId
                        ? equipments.find((e) => e.id === selectedEquipmentId)
                            ?.name
                        : employee.equipmentName || "설비 선택"}
                    </button>

                    {isEquipmentDropdownOpen && (
                      <ul className="equipment-select-dropdown">
                        <li>
                          <button
                            className={`equipment-select-option ${
                              selectedEquipmentId === null ? "selected" : ""
                            }`}
                            onClick={() => {
                              setSelectedEquipmentId(null);
                              setIsEquipmentDropdownOpen(false);
                            }}
                          >
                            설비 없음
                          </button>
                        </li>

                        {equipments.map((eq) => (
                          <li key={eq.id}>
                            <button
                              className={`equipment-select-option ${
                                selectedEquipmentId === eq.id ? "selected" : ""
                              }`}
                              onClick={() => {
                                setSelectedEquipmentId(eq.id);
                                setIsEquipmentDropdownOpen(false);
                              }}
                            >
                              {eq.name}
                            </button>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>

                  <button
                    className="equipment-assign-button"
                    onClick={async () => {
                      if (!employee || !isAdmin || !selectedEquipmentId) return;

                      try {
                        setIsAssigning(true);

                        const res = await assignEquipment(
                          employee.userAccountId,
                          selectedEquipmentId
                        );

                        if (res.success) {
                          alert("설비 지정 완료!");
                          await fetchEmployees?.(null);
                        } else {
                          alert(res.message || "설비 지정 실패");
                        }
                      } catch (e: any) {
                        alert(e.response?.data?.message || "설비 지정 중 오류");
                      } finally {
                        setIsAssigning(false);
                      }
                    }}
                    disabled={isAssigning || !selectedEquipmentId}
                  >
                    {isAssigning ? "지정 중..." : "설비 지정"}
                  </button>
                </div>
              </dd>
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

      {/* 버튼: 연결 요청 */}
      {isAdmin && (
        <button
          className="connect-button"
          onClick={() => setModalType("requestBox")}
        >
          {modalType === "pending" ? "응답 대기 중..." : "연결 요청"}
        </button>
      )}

      {/* 본인일 때 출퇴근 */}
      {!isAdmin && isMine && (
        <button
          className="connect-button"
          onClick={async () => {
            if (isCheckingInOut) return;

            try {
              setIsCheckingInOut(true);

              if (employee.online) {
                await checkOut();
                alert("퇴근 처리 완료");
              } else {
                await checkIn();
                alert("출근 처리 완료");
              }

              await fetchMyInfo?.();
              await fetchEmployees?.(null);
            } finally {
              setIsCheckingInOut(false);
            }
          }}
        >
          {isCheckingInOut ? "처리 중..." : employee.online ? "퇴근" : "출근"}
        </button>
      )}

      {/* 요청 사유 입력 모달 */}
      <Modal
        isOpen={modalType === "requestBox"}
        onClose={() => setModalType(null)}
      >
        <WorkAdd
          title="연결 요청"
          label="요청 사유"
          placeholder="요청 사유 입력"
          buttonText="연결 요청 보내기"
          defaultEmployeeId={employee.userAccountId}
          onSubmit={(desc) => {
            handleConnectionRequest(desc);
            setModalType(null);
          }}
        />
      </Modal>

      {/* pending 모달 */}
      <Modal
        isOpen={modalType === "pending"}
        onClose={closePending}
        contentClassName="modal-content--compact"
      >
        <div className="connection-pending-modal">
          <div className="connection-pending-spinner" />
          <h3 className="connection-pending-title">작업자 응답 대기 중</h3>
          <p className="connection-pending-sub">
            {pendingWorkerName}님에게 요청을 보냈습니다.
            <br />
            응답 시 자동으로 이동합니다.
          </p>

          <div className="connection-pending-info">
            <div className="connection-pending-row">
              <span className="connection-pending-label">작업자</span>
              <span className="connection-pending-value">
                {pendingWorkerName}
              </span>
            </div>

            {pendingEquipmentName && (
              <div className="connection-pending-row">
                <span className="connection-pending-label">설비</span>
                <span className="connection-pending-value">
                  {pendingEquipmentName}
                </span>
              </div>
            )}

            <div className="connection-pending-row">
              <span className="connection-pending-label">경과 시간</span>
              <span className="connection-pending-value">
                {formatElapsedTime(pendingElapsed)}
              </span>
            </div>
          </div>

          {currentRequestDescription && (
            <div className="connection-pending-request">
              <span className="connection-pending-label">요청 사유</span>
              <p className="connection-rejected-request-text">
                {currentRequestDescription}
              </p>
            </div>
          )}

          <button className="connection-pending-close" onClick={closePending}>
            확인
          </button>
        </div>
      </Modal>

      {/* 거절/타임아웃 모달 */}
      <Modal
        isOpen={modalType === "rejected" || modalType === "timeout"}
        onClose={closeRejected}
        contentClassName="modal-content--compact"
      >
        <div
          className="connection-rejected-modal"
          data-cancel-reason={modalType}
        >
          <div className="connection-rejected-icon" />
          <h3 className="connection-rejected-title">
            {modalType === "timeout"
              ? "연결 요청 시간이 초과되었습니다"
              : "작업자가 연결 요청을 거절했습니다"}
          </h3>

          <p className="connection-rejected-sub">
            {modalType === "timeout" ? (
              <>
                {pendingWorkerName}님의 응답을 1분 동안 받지 못했습니다.
                <br />
                다시 요청을 보내주세요.
              </>
            ) : (
              <>
                {pendingWorkerName}님이 요청을 거절했습니다.
                <br />
                필요하다면 다시 요청을 보내세요.
              </>
            )}
          </p>

          {currentRequestDescription && (
            <div className="connection-rejected-request">
              <span className="connection-rejected-label">요청 사유</span>
              <p className="connection-rejected-request-text">
                {currentRequestDescription}
              </p>
            </div>
          )}

          <button className="connection-rejected-close" onClick={closeRejected}>
            확인
          </button>
        </div>
      </Modal>
    </div>
  );
}

export default EmployeeDetail;
