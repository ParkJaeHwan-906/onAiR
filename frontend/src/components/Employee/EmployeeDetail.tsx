import "../../styles/EmployeeDetail.css";
import type { Employee } from "../../types/employee";
import { useUserStore } from "../../store/useUserStore";
import { formatPhone } from "../../utils/formatPhone";
import { sendConnectionRequest } from "../../api/webrtc";
import { useWebRtcRequestStore } from "../../store/useWebRtcRequestStore";
import WorkAdd from "../Work/WorkAdd";
import Modal from "../Work/Modal";
import { useState, useEffect, useRef } from "react";
import { useSSEStore } from "../../store/useSSEStore";
import { getCompanyEquipmentList } from "../../api/equipment";
import { assignEquipment, checkIn, checkOut } from "../../api/user";
import type { Equipment } from "../../types/equipment";

type EmployeeDetailProps = {
  employee: Employee | null;
};

function EmployeeDetail({ employee }: EmployeeDetailProps) {
  const { myInfo, fetchEmployees, fetchMyInfo } = useUserStore();
  const { addSentRequest } = useWebRtcRequestStore();
  const isMine = myInfo?.userAccountId === employee?.userAccountId;
  const isAdmin = myInfo?.role === "관리자";
  const [showRequestBox, setShowRequestBox] = useState(false);
  const { isConnected, connect } = useSSEStore();

  // 설비 지정 관련 상태
  const [equipments, setEquipments] = useState<Equipment[]>([]);
  const [selectedEquipmentId, setSelectedEquipmentId] = useState<number | null>(
    null
  );
  const [isEquipmentDropdownOpen, setIsEquipmentDropdownOpen] = useState(false);
  const [isAssigning, setIsAssigning] = useState(false);
  const [isCheckingInOut, setIsCheckingInOut] = useState(false);
  const equipmentDropdownRef = useRef<HTMLDivElement | null>(null);

  // 요청 기능 사용 전, SSE 연결이 없으면 선연결
  useEffect(() => {
    if (!isConnected) {
      connect();
    }
  }, [isConnected, connect]);

  // 관리자가 직원을 선택했을 때 설비 목록 조회
  useEffect(() => {
    if (isAdmin && employee) {
      fetchEquipments();
      // 현재 직원의 설비 ID 설정
      setSelectedEquipmentId(employee.equipmentId || null);
    }
  }, [isAdmin, employee]);

  // 설비 드롭다운 외부 클릭 감지
  useEffect(() => {
    if (!isEquipmentDropdownOpen) {
      return;
    }

    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as Node;
      if (
        isEquipmentDropdownOpen &&
        equipmentDropdownRef.current &&
        !equipmentDropdownRef.current.contains(target)
      ) {
        setIsEquipmentDropdownOpen(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [isEquipmentDropdownOpen]);

  const fetchEquipments = async () => {
    try {
      const res = await getCompanyEquipmentList();
      if (res.success && res.data) {
        setEquipments(res.data);
      }
    } catch (error) {
      console.error("설비 목록 조회 실패:", error);
    }
  };

  const handleAssignEquipment = async () => {
    if (!employee || !isAdmin) return;

    if (!selectedEquipmentId) {
      alert("설비를 선택해주세요.");
      return;
    }

    try {
      setIsAssigning(true);
      const res = await assignEquipment(
        employee.userAccountId,
        selectedEquipmentId
      );

      if (res.success) {
        alert("설비가 성공적으로 지정되었습니다.");
        // 직원 목록 새로고침
        if (fetchEmployees) {
          await fetchEmployees(null);
          // 직원 목록 새로고침 후 선택한 직원 정보도 업데이트
          // (useUserStore의 employees 배열이 업데이트되므로 부모 컴포넌트에서 처리 필요)
        }
      } else {
        alert(res.message || "설비 지정에 실패했습니다.");
      }
    } catch (error: any) {
      console.error("설비 지정 실패:", error);
      alert(
        error.response?.data?.message || "설비 지정 중 오류가 발생했습니다."
      );
    } finally {
      setIsAssigning(false);
    }
  };

  // 연결 요청 핸들러
  const handleConnectionRequest = async (_description: string) => {
    if (!employee || !isAdmin) return;

    try {
      // 혹시 연결이 끊겨있다면 재연결 시도
      if (!isConnected) connect();

      // 연결 요청 전송 (description은 현재 빈 문자열로 전송)
      const res = await sendConnectionRequest(employee.userAccountId);

      if (!res.success) {
        const errorMsg = res.message || "연결 요청 중 오류가 발생했습니다.";
        console.error("연결 요청 실패:", errorMsg);
        alert(errorMsg + "\n\n작업자가 SSE 연결이 되어 있는지 확인해주세요.");
        return;
      }

      // 관리자가 보낸 요청 정보를 sentRequests에 저장 (응답을 받을 때 매칭하기 위해)
      // 상대방(작업자) 정보도 함께 저장하여 CommunicationPage에서 사용
      if (myInfo && employee) {
        addSentRequest(
          {
            senderAccountId: myInfo.userAccountId,
            name: myInfo.name,
            phone: myInfo.phone || "",
            equipmentName: myInfo.equipmentName || null,
          },
          {
            senderAccountId: employee.userAccountId,
            name: employee.name,
            phone: employee.phone || "",
            equipmentName: employee.equipmentName || null,
          }
        );
      }

      alert("연결 요청이 성공적으로 전송되었습니다.");
      // 요청만 보내고 응답을 기다림 (SSE로 토큰을 받을 예정)
      // 백엔드에서 작업자에게 SSE로 전달되며, 작업자는 HomePage의 요청 목록에서 확인 가능
      // 관리자가 보낸 요청은 자신의 요청 목록에 표시되지 않음 (작업자의 요청 목록에만 표시됨)
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
          <>
            <div className="detail-item">
              <dt>담당 설비</dt>
              <dd>{employee.equipmentName || "미지정"}</dd>
            </div>
            <div className="detail-item">
              <dt>설비 지정</dt>
              <dd>
                <div
                  className="equipment-assign-wrapper"
                  ref={equipmentDropdownRef}
                >
                  <button
                    type="button"
                    className={`equipment-select-trigger${
                      isEquipmentDropdownOpen ? " open" : ""
                    }`}
                    onClick={() => setIsEquipmentDropdownOpen((prev) => !prev)}
                    disabled={isAssigning}
                  >
                    {selectedEquipmentId
                      ? equipments.find((eq) => eq.id === selectedEquipmentId)
                          ?.name || "설비를 선택하세요"
                      : "설비를 선택하세요"}
                  </button>
                  {isEquipmentDropdownOpen && (
                    <ul className="equipment-select-dropdown">
                      <li>
                        <button
                          type="button"
                          className={`equipment-select-option${
                            selectedEquipmentId === null ? " selected" : ""
                          }`}
                          onClick={() => {
                            setSelectedEquipmentId(null);
                            setIsEquipmentDropdownOpen(false);
                          }}
                        >
                          <span>설비 없음</span>
                        </button>
                      </li>
                      {equipments.map((equipment) => (
                        <li key={equipment.id}>
                          <button
                            type="button"
                            className={`equipment-select-option${
                              equipment.id === selectedEquipmentId
                                ? " selected"
                                : ""
                            }`}
                            onClick={() => {
                              setSelectedEquipmentId(equipment.id);
                              setIsEquipmentDropdownOpen(false);
                            }}
                          >
                            <span className="equipment-select-option-title">
                              {equipment.name}
                            </span>
                            <span className="equipment-select-option-meta">
                              {equipment.category}
                            </span>
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
                <button
                  className="equipment-assign-button"
                  onClick={handleAssignEquipment}
                  disabled={isAssigning || !selectedEquipmentId}
                >
                  {isAssigning ? "지정 중..." : "설비 지정"}
                </button>
              </dd>
            </div>
          </>
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

      {!isAdmin && isMine && (
        <>
          <button
            className="connect-button"
            onClick={async () => {
              if (isCheckingInOut) return;

              try {
                setIsCheckingInOut(true);

                if (employee.online) {
                  // 퇴근 처리
                  await checkOut();
                  alert("퇴근 처리되었습니다.");
                } else {
                  // 출근 처리
                  await checkIn();
                  alert("출근 처리되었습니다.");
                }

                // 내 정보 새로고침 (작업자가 자신의 정보를 볼 때)
                if (fetchMyInfo) {
                  await fetchMyInfo();
                }

                // 직원 목록 새로고침 (관리자가 볼 때를 위해)
                if (fetchEmployees) {
                  await fetchEmployees(null);
                }
              } catch (error: any) {
                const errorMessage =
                  error.response?.data?.message ||
                  error.message ||
                  "처리 중 오류가 발생했습니다.";
                alert(errorMessage);
              } finally {
                setIsCheckingInOut(false);
              }
            }}
            disabled={isCheckingInOut}
          >
            {isCheckingInOut ? "처리 중..." : employee.online ? "퇴근" : "출근"}
          </button>
        </>
      )}
    </div>
  );
}

export default EmployeeDetail;
