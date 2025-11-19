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
import { useNavigate } from "react-router-dom";

type EmployeeDetailProps = {
  employee: Employee | null;
};

type ModalType = "pending" | "rejected" | "timeout" | "requestBox" | null;

function EmployeeDetail({ employee }: EmployeeDetailProps) {
  // ---------------------------
  // 글로벌 스토어
  // ---------------------------
  const { myInfo, fetchEmployees, fetchMyInfo } = useUserStore();
  const { addSentRequest, sentRequests } = useWebRtcRequestStore();
  const { clearEvents } = useSSEEventsStore();
  const { isConnected, connect } = useSSEStore();

  // ---------------------------
  // 현재 로그인한 사람이 누구인지
  // ---------------------------
  const isMine = myInfo?.userAccountId === employee?.userAccountId;
  const isAdmin = myInfo?.role === "관리자";

  // ---------------------------
  // 모달 상태 및 요청 관련 상태
  // ---------------------------
  const [modalType, setModalType] = useState<ModalType>(null);
  const [currentRequestDescription, setCurrentRequestDescription] =
    useState(""); // 요청 사유
  const [pendingElapsed, setPendingElapsed] = useState(0); // 대기 시간 표시
  const [hasDismissedPending, setHasDismissedPending] = useState(false); // 대기 모달 닫음 여부
  const pendingStartRef = useRef<number | null>(null); // 요청 시작 시간 저장

  // ---------------------------
  // 설비 관련 UI 상태
  // ---------------------------
  const [equipments, setEquipments] = useState<Equipment[]>([]);
  const [selectedEquipmentId, setSelectedEquipmentId] = useState<number | null>(
    null
  );
  const [isEquipmentDropdownOpen, setIsEquipmentDropdownOpen] = useState(false);
  const equipmentDropdownRef = useRef<HTMLDivElement | null>(null);
  const [isAssigning, setIsAssigning] = useState(false); // 설비 지정 처리 중 여부
  const [isCheckingInOut, setIsCheckingInOut] = useState(false); // 출퇴근 처리 중 여부

  const navigate = useNavigate();

  // ---------------------------
  // activeRequest: 이 직원에게 보낸 요청 중 최신 요청
  // ---------------------------
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

  // 표시용 이름/설비명
  const pendingWorkerName =
    activeRequest?.receiverInfo?.name || employee?.name || "";
  const pendingEquipmentName =
    activeRequest?.receiverInfo?.equipmentName || employee?.equipmentName;

  // ---------------------------
  // SSE 이벤트: 작업자가 수락 / 거절 / 타임아웃
  // ---------------------------
  useEffect(() => {
    if (!isAdmin) return;

    // 통신 응답 이벤트
    const handleCallResponse = (e: any) => {
      const { acceptConnection, accessToken } = e.detail;

      // console.log("SSE 응답:", e.detail);

      // 수락됨
      if (acceptConnection && accessToken) {
        setModalType(null);
        // // 리퀘스트 상태 갱신
        useWebRtcRequestStore
          .getState()
          .updateSentRequestStatus(true, accessToken);

        // 통신 화면으로 이동
        navigate("/communication", {
          state: {
            token: accessToken,
            partnerInfo: {
              senderAccountId: employee?.userAccountId,
              name: employee?.name,
              phone: employee?.phone,
              equipmentName: employee?.equipmentName,
            },
          },
        });
        return;
      }

      // 거절됨
      // console.log("통신 거절 이벤트:", e.detail);
      useWebRtcRequestStore.getState().updateSentRequestStatus(false);
      setModalType("rejected");
    };

    // 타임아웃
    const handleTimeout = (_e: any) => {
      // console.log("통신 타임아웃", e.detail);

      // 이미 거절 모달 뜬 상태면 → timeout 무시
      if (modalType === "rejected") return;

      // 이미 timeout 모달 뜬 상태면 중복 방지
      if (modalType === "timeout") return;

      // 진짜 pending 중 타임아웃 → 모달 표시
      setModalType("timeout");
    };

    window.addEventListener("callResponse", handleCallResponse);
    window.addEventListener("rtcCanceled", handleTimeout);

    return () => {
      window.removeEventListener("callResponse", handleCallResponse);
      window.removeEventListener("rtcCanceled", handleTimeout);
    };
  }, [isAdmin, employee, navigate]);

  // ---------------------------
  // pending 상태면 자동으로 모달 열기
  // ---------------------------
  useEffect(() => {
    if (!isAdmin) return;

    // 요청 사유 입력 모달이면 건드리지 않음
    if (modalType === "requestBox") return;

    // 거절 상태면 pending 다시 못 열게만 막기
    if (modalType === "rejected") return;

    // timeout 상태면 pending 다시 못 열게만 막기
    if (modalType === "timeout") return;

    // pending 요청 존재 → 자동으로 pending 모달 활성화
    if (isPending && activeRequest) {
      pendingStartRef.current = new Date(activeRequest.requestTime).getTime();
      setCurrentRequestDescription(activeRequest.description ?? "");
      if (modalType !== "pending") {
        setModalType("pending");
      }
      return;
    }
  }, [isAdmin, modalType, isPending, activeRequest, hasDismissedPending]);

  // ---------------------------
  // pending 경과 시간 업데이트 (1초마다)
  // ---------------------------
  useEffect(() => {
    if (!isPending) return;

    const start = pendingStartRef.current;
    if (!start) return;

    const tick = () => {
      setPendingElapsed(Math.floor((Date.now() - start) / 1000));
    };

    tick(); // 첫 즉시 반영

    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [isPending]);

  // 경과 시간 mm:ss 로 표시
  const formatElapsedTime = (sec: number) => {
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  };

  // ---------------------------
  // SSE 자동 연결
  // ---------------------------
  useEffect(() => {
    if (!isConnected) connect();
  }, [isConnected, connect]);

  // ---------------------------
  // 설비 목록 조회
  // ---------------------------
  useEffect(() => {
    if (isAdmin && employee) {
      loadEquipments();
      setSelectedEquipmentId(employee.equipmentId || null);
    }
  }, [isAdmin, employee]);

  // 설비 리스트 API 호출
  const loadEquipments = async () => {
    try {
      const res = await getCompanyEquipmentList();
      if (res.success && res.data) {
        setEquipments(res.data);
      }
    } catch (e) {
      console.error("설비 조회 실패: ", e);
    }
  };

  // ---------------------------
  // 연결 요청 보내기 (관리자가 작업자에게)
  // ---------------------------
  const handleConnectionRequest = async (description: string) => {
    if (!employee || !isAdmin) return;

    try {
      if (!isConnected) connect();

      // 요청 API
      const res = await sendConnectionRequest(
        employee.userAccountId,
        description
      );

      if (!res.success) {
        alert("연결 요청 실패 — 작업자 SSE 연결 상태 확인 필요");
        return;
      }

      // 요청 스토어에 저장
      if (myInfo) {
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

      // pending 상태 시작
      pendingStartRef.current = Date.now();
      setCurrentRequestDescription(description);
      setPendingElapsed(0);
      setHasDismissedPending(false);
      setModalType("pending");
    } catch {
      alert("요청 중 오류 발생");
    }
  };

  // ---------------------------
  // 모달 닫기 핸들러
  // ---------------------------
  // const closePending = () => {
  //   setHasDismissedPending(true);
  //   clearEvents();
  //   setModalType(null);
  // };

  // const closeRejected = () => {
  //   clearEvents();
  //   setModalType(null);
  // };

  const closeModal = () => {
    clearEvents();
    setModalType(null);
  };

  // ==========================================================
  // 통합 모달 렌더링 (pending + rejected + timeout)
  // ==========================================================
  const renderModalContent = () => {
    if (modalType === "requestBox") return null;

    const isTimeout = modalType === "timeout";
    const isRejected = modalType === "rejected";
    const isPendingModal = modalType === "pending";

    // -------- pending 모달 --------
    if (isPendingModal) {
      return (
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

          <button className="connection-pending-close" onClick={closeModal}>
            확인
          </button>
        </div>
      );
    }

    // -------- 거절/타임아웃 모달 --------
    if (isRejected || isTimeout) {
      return (
        <div
          className="connection-rejected-modal"
          data-cancel-reason={modalType}
        >
          <div className="connection-rejected-icon" />
          <h3 className="connection-rejected-title">
            {isTimeout
              ? "연결 요청 시간이 초과되었습니다"
              : "작업자가 연결 요청을 거절했습니다"}
          </h3>

          <p className="connection-rejected-sub">
            {isTimeout ? (
              <>
                {pendingWorkerName}님의 응답을 1분 동안 받지 못했습니다.
                <br />
                다시 요청을 보내주세요.
              </>
            ) : (
              <>
                {pendingWorkerName}님이 요청을 거절했습니다.
                <br />
                필요하다면 다시 요청하세요.
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

          <button className="connection-rejected-close" onClick={closeModal}>
            확인
          </button>
        </div>
      );
    }

    return null;
  };

  // ---------------------------
  // 직원 정보 없을 때
  // ---------------------------
  if (!employee) {
    return (
      <div className="detail-wrapper">
        <div className="detail-header">직원 상세 정보</div>
        <span className="detail-empty">직원을 선택해주세요.</span>
      </div>
    );
  }

  // ==========================================================
  // 메인 렌더링
  // ==========================================================
  return (
    <div className="detail-wrapper">
      <div className="detail-header">직원 상세 정보</div>

      {/* 프로필 */}
      <div className="profile-section">
        <img src={"images/default-profile.png"} className="profile-img" />
        <h2 className="detail-title">{employee.name}</h2>
        <p className="detail-email">{employee.email}</p>
      </div>

      {/* 직원 정보 리스트 */}
      <dl className="detail-list">
        <div className="detail-item">
          <dt>부서</dt>
          <dd>{employee.part || "미등록"}</dd>
        </div>

        <div className="detail-item">
          <dt>연락처</dt>
          <dd>{formatPhone(employee.phone)}</dd>
        </div>

        {/* 관리자일 때만 설비 정보 */}
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
                  {/* 설비 선택 드롭다운 */}
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

                  {/* 설비 지정 버튼 */}
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
                        alert(e.response?.data?.message || "설비 지정 오류");
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

        {/* 근무 상태 */}
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

      {/* 관리자 → 연결 요청 버튼 */}
      {isAdmin && (
        <button
          className="connect-button"
          onClick={() => setModalType("requestBox")}
        >
          {modalType === "pending" ? "응답 대기 중..." : "연결 요청"}
        </button>
      )}

      {/* 작업자 본인 → 출퇴근 처리 버튼 */}
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
          defaultEquipmentId={employee.equipmentId}
          defaultEmployeeId={employee.userAccountId}
          onSubmit={(desc) => {
            handleConnectionRequest(desc);
            setModalType(null);
          }}
        />
      </Modal>

      {/* 통합 모달: pending / rejected / timeout */}
      <Modal
        isOpen={
          modalType === "pending" ||
          modalType === "rejected" ||
          modalType === "timeout"
        }
        onClose={closeModal}
        contentClassName="modal-content--compact"
      >
        {renderModalContent()}
      </Modal>
    </div>
  );
}

export default EmployeeDetail;
