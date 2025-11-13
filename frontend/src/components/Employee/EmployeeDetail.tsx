// import "../../styles/EmployeeDetail.css";
// import type { Employee } from "../../types/employee";
// import { useUserStore } from "../../store/useUserStore";
// import { formatPhone } from "../../utils/formatPhone";
// import { sendConnectionRequest } from "../../api/webrtc";
// import { useWebRtcRequestStore } from "../../store/useWebRtcRequestStore";
// import WorkAdd from "../Work/WorkAdd";
// import Modal from "../Work/Modal";
// import { useState, useEffect, useRef, useMemo } from "react";
// import { useSSEStore } from "../../store/useSSEStore";
// import { getCompanyEquipmentList } from "../../api/equipment";
// import { assignEquipment, checkIn, checkOut } from "../../api/user";
// import type { Equipment } from "../../types/equipment";

// type EmployeeDetailProps = {
//   employee: Employee | null;
// };

// type ModalType = "pending" | "rejected" | "timeout" | "requestBox" | null;

// function EmployeeDetail({ employee }: EmployeeDetailProps) {
//   const { myInfo, fetchEmployees, fetchMyInfo } = useUserStore();
//   const { addSentRequest, sentRequests } = useWebRtcRequestStore();
//   const isMine = myInfo?.userAccountId === employee?.userAccountId;
//   const isAdmin = myInfo?.role === "관리자";

//   const [showRequestBox, setShowRequestBox] = useState(false);
//   const { isConnected, connect } = useSSEStore();

//   // 설비 지정 관련 상태
//   const [equipments, setEquipments] = useState<Equipment[]>([]);
//   const [selectedEquipmentId, setSelectedEquipmentId] = useState<number | null>(
//     null
//   );
//   const [isEquipmentDropdownOpen, setIsEquipmentDropdownOpen] = useState(false);
//   const [isAssigning, setIsAssigning] = useState(false);
//   const [isCheckingInOut, setIsCheckingInOut] = useState(false);
//   const equipmentDropdownRef = useRef<HTMLDivElement | null>(null);
//   const pendingFallbackStartRef = useRef<number | null>(null);
//   const [isPendingModalOpen, setIsPendingModalOpen] = useState(false);
//   const [hasDismissedPending, setHasDismissedPending] = useState(false);
//   const [pendingElapsed, setPendingElapsed] = useState(0);
//   const [currentRequestDescription, setCurrentRequestDescription] =
//     useState("");
//   const [isRejectedModalOpen, setIsRejectedModalOpen] = useState(false);
//   const [cancelReason, setCancelReason] = useState<
//     "rejected" | "timeout" | null
//   >(null);

//   // acknowledged된 요청 ID를 localStorage에 저장하는 함수
//   const saveAcknowledgedRequestId = (requestId: string) => {
//     try {
//       const stored = localStorage.getItem("acknowledgedRejectedRequests");
//       const acknowledgedIds: string[] = stored ? JSON.parse(stored) : [];
//       if (!acknowledgedIds.includes(requestId)) {
//         acknowledgedIds.push(requestId);
//         localStorage.setItem(
//           "acknowledgedRejectedRequests",
//           JSON.stringify(acknowledgedIds)
//         );
//       }
//     } catch (error) {
//       console.error("acknowledgedRejectedRequests 저장 실패:", error);
//     }
//   };

//   // acknowledged된 요청 ID인지 확인하는 함수
//   const isAcknowledged = (requestId: string | null): boolean => {
//     if (!requestId) return false;
//     try {
//       const stored = localStorage.getItem("acknowledgedRejectedRequests");
//       const acknowledgedIds = stored ? JSON.parse(stored) : [];
//       return acknowledgedIds.includes(requestId);
//     } catch {
//       return false;
//     }
//   };

//   const activeRequest = useMemo(() => {
//     if (!isAdmin || !employee) return null;
//     const related = sentRequests.filter(
//       (req) => req.receiverInfo?.senderAccountId === employee.userAccountId
//     );
//     if (related.length === 0) return null;
//     return related.sort(
//       (a, b) =>
//         new Date(b.requestTime).getTime() - new Date(a.requestTime).getTime()
//     )[0];
//   }, [isAdmin, employee, sentRequests]);

//   const isPendingRequest = activeRequest?.status === "pending";
//   const isRejectedRequest = activeRequest?.status === "rejected";
//   const isTimeoutRequest = activeRequest?.status === "timeout";
//   const activeRequestId = activeRequest?.id ?? null;

//   const pendingWorkerName =
//     activeRequest?.receiverInfo?.name || employee?.name || "";
//   const pendingEquipmentName =
//     activeRequest?.receiverInfo?.equipmentName || employee?.equipmentName;

//   useEffect(() => {
//     if (activeRequest?.description) {
//       setCurrentRequestDescription(activeRequest.description);
//     }
//   }, [activeRequest]);

//   useEffect(() => {
//     if (!isAdmin) return;

//     if (isPendingRequest && activeRequest) {
//       pendingFallbackStartRef.current = new Date(
//         activeRequest.requestTime
//       ).getTime();
//       setCurrentRequestDescription(activeRequest.description ?? "");
//       if (!hasDismissedPending) {
//         setIsPendingModalOpen(true);
//       }
//       setIsRejectedModalOpen(false);
//       return;
//     }

//     if (isRejectedRequest && activeRequest) {
//       pendingFallbackStartRef.current = null;
//       setPendingElapsed(0);
//       setCurrentRequestDescription(activeRequest.description ?? "");
//       setIsPendingModalOpen(false);
//       setCancelReason("rejected");
//       if (!isAcknowledged(activeRequestId)) {
//         setIsRejectedModalOpen(true);
//       } else {
//         setIsRejectedModalOpen(false);
//       }
//       return;
//     }

//     if (isTimeoutRequest && activeRequest) {
//       pendingFallbackStartRef.current = null;
//       setPendingElapsed(0);
//       setCurrentRequestDescription(activeRequest.description ?? "");
//       setIsPendingModalOpen(false);
//       setCancelReason("timeout");
//       if (!isAcknowledged(activeRequestId)) {
//         setIsRejectedModalOpen(true);
//       } else {
//         setIsRejectedModalOpen(false);
//       }
//       return;
//     }

//     setIsPendingModalOpen(false);
//     setIsRejectedModalOpen(false);
//     setHasDismissedPending(false);
//     setPendingElapsed(0);
//     pendingFallbackStartRef.current = null;
//     setCurrentRequestDescription("");
//     setCancelReason(null);
//   }, [
//     isAdmin,
//     isPendingRequest,
//     isRejectedRequest,
//     isTimeoutRequest,
//     activeRequest,
//     activeRequestId,
//     hasDismissedPending,
//   ]);

//   useEffect(() => {
//     if (!isAdmin) return;
//     const startTimestamp =
//       (isPendingRequest && activeRequest
//         ? new Date(activeRequest.requestTime).getTime()
//         : pendingFallbackStartRef.current) ?? null;

//     if (!startTimestamp) return;

//     const updateElapsed = () => {
//       const diff = Math.max(0, Date.now() - startTimestamp);
//       setPendingElapsed(Math.floor(diff / 1000));
//     };

//     updateElapsed();
//     const interval = window.setInterval(updateElapsed, 1000);
//     return () => window.clearInterval(interval);
//   }, [isAdmin, isPendingRequest, activeRequest]);

//   const formatElapsedTime = (seconds: number) => {
//     const minutes = Math.floor(seconds / 60);
//     const remain = seconds % 60;
//     return `${String(minutes).padStart(2, "0")}:${String(remain).padStart(
//       2,
//       "0"
//     )}`;
//   };

//   // 요청 기능 사용 전, SSE 연결이 없으면 선연결
//   useEffect(() => {
//     if (!isConnected) {
//       connect();
//     }
//   }, [isConnected, connect]);

//   // 관리자가 직원을 선택했을 때 설비 목록 조회
//   useEffect(() => {
//     if (isAdmin && employee) {
//       fetchEquipments();
//       // 현재 직원의 설비 ID 설정
//       setSelectedEquipmentId(employee.equipmentId || null);
//     }
//   }, [isAdmin, employee]);

//   // 설비 드롭다운 외부 클릭 감지
//   useEffect(() => {
//     if (!isEquipmentDropdownOpen) {
//       return;
//     }

//     const handleClickOutside = (event: MouseEvent) => {
//       const target = event.target as Node;
//       if (
//         isEquipmentDropdownOpen &&
//         equipmentDropdownRef.current &&
//         !equipmentDropdownRef.current.contains(target)
//       ) {
//         setIsEquipmentDropdownOpen(false);
//       }
//     };

//     document.addEventListener("mousedown", handleClickOutside);
//     return () => {
//       document.removeEventListener("mousedown", handleClickOutside);
//     };
//   }, [isEquipmentDropdownOpen]);

//   const fetchEquipments = async () => {
//     try {
//       const res = await getCompanyEquipmentList();
//       if (res.success && res.data) {
//         setEquipments(res.data);
//       }
//     } catch (error) {
//       console.error("설비 목록 조회 실패:", error);
//     }
//   };

//   const handleAssignEquipment = async () => {
//     if (!employee || !isAdmin) return;

//     if (!selectedEquipmentId) {
//       alert("설비를 선택해주세요.");
//       return;
//     }

//     try {
//       setIsAssigning(true);
//       const res = await assignEquipment(
//         employee.userAccountId,
//         selectedEquipmentId
//       );

//       if (res.success) {
//         alert("설비가 성공적으로 지정되었습니다.");
//         // 직원 목록 새로고침
//         if (fetchEmployees) {
//           await fetchEmployees(null);
//           // 직원 목록 새로고침 후 선택한 직원 정보도 업데이트
//           // (useUserStore의 employees 배열이 업데이트되므로 부모 컴포넌트에서 처리 필요)
//         }
//       } else {
//         alert(res.message || "설비 지정에 실패했습니다.");
//       }
//     } catch (error: any) {
//       console.error("설비 지정 실패:", error);
//       alert(
//         error.response?.data?.message || "설비 지정 중 오류가 발생했습니다."
//       );
//     } finally {
//       setIsAssigning(false);
//     }
//   };

//   // 연결 요청 핸들러
//   const handleConnectionRequest = async (description: string) => {
//     if (!employee || !isAdmin) return;

//     try {
//       // 혹시 연결이 끊겨있다면 재연결 시도
//       if (!isConnected) connect();

//       // 연결 요청 전송 (description은 현재 빈 문자열로 전송)
//       const res = await sendConnectionRequest(employee.userAccountId);

//       if (!res.success) {
//         const errorMsg = res.message || "연결 요청 중 오류가 발생했습니다.";
//         console.error("연결 요청 실패:", errorMsg);
//         alert(errorMsg + "\n\n작업자가 SSE 연결이 되어 있는지 확인해주세요.");
//         return;
//       }

//       // 관리자가 보낸 요청 정보를 sentRequests에 저장 (응답을 받을 때 매칭하기 위해)
//       // 상대방(작업자) 정보도 함께 저장하여 CommunicationPage에서 사용
//       if (myInfo && employee) {
//         addSentRequest(
//           {
//             senderAccountId: myInfo.userAccountId,
//             name: myInfo.name,
//             phone: myInfo.phone || "",
//             equipmentName: myInfo.equipmentName || null,
//             description,
//           },
//           {
//             senderAccountId: employee.userAccountId,
//             name: employee.name,
//             phone: employee.phone || "",
//             equipmentName: employee.equipmentName || null,
//           }
//         );
//       }

//       setCurrentRequestDescription(description);
//       pendingFallbackStartRef.current = Date.now();
//       setHasDismissedPending(false);
//       setPendingElapsed(0);
//       setIsPendingModalOpen(true);
//       setIsRejectedModalOpen(false);
//       // 요청만 보내고 응답을 기다림 (SSE로 토큰을 받을 예정)
//       // 백엔드에서 작업자에게 SSE로 전달되며, 작업자는 HomePage의 요청 목록에서 확인 가능
//       // 관리자가 보낸 요청은 자신의 요청 목록에 표시되지 않음 (작업자의 요청 목록에만 표시됨)
//     } catch (error) {
//       console.error("연결 요청 중 오류:", error);
//       alert("요청 처리 중 오류가 발생했습니다.");
//     }
//   };

//   const handleConnectButtonClick = () => {
//     if (isPendingRequest) {
//       setHasDismissedPending(false);
//       setIsPendingModalOpen(true);
//       return;
//     }
//     if (
//       (isRejectedRequest || isTimeoutRequest) &&
//       activeRequestId &&
//       !isAcknowledged(activeRequestId)
//     ) {
//       setIsRejectedModalOpen(true);
//       return;
//     }
//     setShowRequestBox(true);
//   };

//   const handlePendingModalClose = () => {
//     setIsPendingModalOpen(false);
//     setHasDismissedPending(true);
//   };

//   const handleRejectedModalClose = () => {
//     setIsRejectedModalOpen(false);
//     if (activeRequestId) {
//       saveAcknowledgedRequestId(activeRequestId);
//     }
//     setCancelReason(null);
//   };

//   if (!employee) {
//     return (
//       <div className="detail-wrapper">
//         <div className="detail-header">직원 상세 정보</div>
//         <span className="detail-empty">직원을 선택해주세요.</span>
//       </div>
//     );
//   }

//   return (
//     <div className="detail-wrapper">
//       <div className="detail-header">직원 상세 정보</div>

//       <div className="profile-section">
//         <img
//           src={"images/default-profile.png"}
//           alt="프로필"
//           className="profile-img"
//         />
//         <h2 className="detail-title">{employee.name}</h2>
//         <p className="detail-email">{employee.email}</p>
//       </div>

//       <dl className="detail-list">
//         <div className="detail-item">
//           <dt>부서</dt>
//           <dd>{employee.part || "미등록"}</dd>
//         </div>
//         <div className="detail-item">
//           <dt>연락처</dt>
//           <dd>{formatPhone(employee.phone)}</dd>
//         </div>

//         {isAdmin && (
//           <>
//             <div className="detail-item">
//               <dt>담당 설비</dt>
//               <dd>{employee.equipmentName || "미지정"}</dd>
//             </div>
//             <div className="detail-item">
//               <dt>설비 지정</dt>
//               <dd>
//                 <div className="equipment-assign-row">
//                   <div
//                     className="equipment-assign-wrapper"
//                     ref={equipmentDropdownRef}
//                   >
//                     <button
//                       type="button"
//                       className={`equipment-select-trigger${
//                         isEquipmentDropdownOpen ? " open" : ""
//                       }`}
//                       onClick={() =>
//                         setIsEquipmentDropdownOpen((prev) => !prev)
//                       }
//                       disabled={isAssigning}
//                     >
//                       {selectedEquipmentId
//                         ? equipments.find((eq) => eq.id === selectedEquipmentId)
//                             ?.name || "설비를 선택하세요"
//                         : employee.equipmentName || "설비를 선택하세요"}
//                     </button>
//                     {isEquipmentDropdownOpen && (
//                       <ul className="equipment-select-dropdown">
//                         <li>
//                           <button
//                             type="button"
//                             className={`equipment-select-option${
//                               selectedEquipmentId === null ? " selected" : ""
//                             }`}
//                             onClick={() => {
//                               setSelectedEquipmentId(null);
//                               setIsEquipmentDropdownOpen(false);
//                             }}
//                           >
//                             <span>설비 없음</span>
//                           </button>
//                         </li>
//                         {equipments.map((equipment) => (
//                           <li key={equipment.id}>
//                             <button
//                               type="button"
//                               className={`equipment-select-option${
//                                 equipment.id === selectedEquipmentId
//                                   ? " selected"
//                                   : ""
//                               }`}
//                               onClick={() => {
//                                 setSelectedEquipmentId(equipment.id);
//                                 setIsEquipmentDropdownOpen(false);
//                               }}
//                             >
//                               <span className="equipment-select-option-title">
//                                 {equipment.name}
//                               </span>
//                               <span className="equipment-select-option-meta">
//                                 {equipment.category}
//                               </span>
//                             </button>
//                           </li>
//                         ))}
//                       </ul>
//                     )}
//                   </div>
//                   <button
//                     className="equipment-assign-button"
//                     onClick={handleAssignEquipment}
//                     disabled={isAssigning || !selectedEquipmentId}
//                   >
//                     {isAssigning ? "지정 중..." : "설비 지정"}
//                   </button>
//                 </div>
//               </dd>
//             </div>
//           </>
//         )}

//         {!isAdmin && isMine && (
//           <>
//             <div className="detail-item">
//               <dt>회사</dt>
//               <dd>{employee.company}</dd>
//             </div>
//             <div className="detail-item">
//               <dt>생년월일</dt>
//               <dd>{employee.birth || "등록되지 않음"}</dd>
//             </div>
//           </>
//         )}

//         <div className="detail-item">
//           <dt>근무 상태</dt>
//           <dd>
//             <span
//               className="detail-status"
//               data-online={employee.online ? "true" : "false"}
//             >
//               {employee.online ? "온라인" : "오프라인"}
//             </span>
//           </dd>
//         </div>
//       </dl>

//       {/* 모달로 변경 */}
//       {isAdmin && (
//         <>
//           <button
//             className="connect-button"
//             data-status={
//               isPendingRequest
//                 ? "pending"
//                 : (isRejectedRequest || isTimeoutRequest) &&
//                   activeRequestId &&
//                   !isAcknowledged(activeRequestId)
//                 ? "rejected"
//                 : "idle"
//             }
//             onClick={handleConnectButtonClick}
//           >
//             {isPendingRequest
//               ? "응답 대기 중..."
//               : (isRejectedRequest || isTimeoutRequest) &&
//                 activeRequestId &&
//                 !isAcknowledged(activeRequestId)
//               ? isTimeoutRequest
//                 ? "요청 시간이 초과되었습니다"
//                 : "요청이 거절되었습니다"
//               : "연결 요청"}
//           </button>

//           <Modal
//             isOpen={showRequestBox}
//             onClose={() => setShowRequestBox(false)}
//           >
//             <WorkAdd
//               title="연결 요청"
//               label="요청 사유"
//               placeholder="요청 사유를 입력하세요."
//               buttonText="연결 요청 보내기"
//               defaultEquipmentId={employee.equipmentId}
//               defaultEquipmentLabel={
//                 employee.equipmentName
//                   ? employee.equipmentCategoryName
//                     ? `${employee.equipmentName} (${employee.equipmentCategoryName})`
//                     : employee.equipmentName
//                   : undefined
//               }
//               defaultEmployeeId={employee.userAccountId}
//               defaultEmployeeLabel={
//                 employee.part
//                   ? `${employee.name} (${employee.part})`
//                   : employee.name
//               }
//               onSubmit={(text) => {
//                 handleConnectionRequest(text);
//                 setShowRequestBox(false);
//               }}
//             />
//           </Modal>

//           <Modal
//             isOpen={isPendingModalOpen}
//             onClose={handlePendingModalClose}
//             contentClassName="modal-content--compact"
//           >
//             <div className="connection-pending-modal">
//               <div className="connection-pending-spinner" aria-hidden="true" />
//               <h3 className="connection-pending-title">
//                 작업자 응답을 기다리는 중입니다
//               </h3>
//               <p className="connection-pending-sub">
//                 {pendingWorkerName}님에게 연결 요청을 전송했습니다.
//                 <br />
//                 응답이 도착하면 자동으로 통화 화면으로 이동합니다.
//               </p>

//               <div className="connection-pending-info">
//                 <div className="connection-pending-row">
//                   <span className="connection-pending-label">작업자</span>
//                   <span className="connection-pending-value">
//                     {pendingWorkerName}
//                   </span>
//                 </div>
//                 {pendingEquipmentName && (
//                   <div className="connection-pending-row">
//                     <span className="connection-pending-label">담당 설비</span>
//                     <span className="connection-pending-value">
//                       {pendingEquipmentName}
//                     </span>
//                   </div>
//                 )}
//                 <div className="connection-pending-row">
//                   <span className="connection-pending-label">경과 시간</span>
//                   <span className="connection-pending-timer">
//                     {formatElapsedTime(pendingElapsed)}
//                   </span>
//                 </div>
//               </div>

//               {currentRequestDescription && (
//                 <div className="connection-pending-request">
//                   <span className="connection-pending-label">요청 사유</span>
//                   <p className="connection-pending-request-text">
//                     {currentRequestDescription}
//                   </p>
//                 </div>
//               )}

//               <button
//                 type="button"
//                 className="connection-pending-close"
//                 onClick={handlePendingModalClose}
//               >
//                 확인
//               </button>
//             </div>
//           </Modal>

//           <Modal
//             isOpen={isRejectedModalOpen}
//             onClose={handleRejectedModalClose}
//             contentClassName="modal-content--compact"
//           >
//             <div
//               className="connection-rejected-modal"
//               data-cancel-reason={cancelReason}
//             >
//               <div
//                 className="connection-rejected-icon"
//                 aria-hidden="true"
//               ></div>
//               <h3 className="connection-rejected-title">
//                 {cancelReason === "timeout"
//                   ? "연결 요청 시간이 초과되었습니다"
//                   : "작업자가 연결 요청을 거절했습니다"}
//               </h3>
//               <p className="connection-rejected-sub">
//                 {cancelReason === "timeout" ? (
//                   <>
//                     {pendingWorkerName}님의 응답을 1분 동안 받지 못했습니다.
//                     <br />
//                     필요하시다면 다시 요청을 보내주세요.
//                   </>
//                 ) : (
//                   <>
//                     {pendingWorkerName}님이 해당 요청에 응답하지 않았습니다.
//                     <br />
//                     필요하시다면 다시 요청을 보내주세요.
//                   </>
//                 )}
//               </p>
//               {currentRequestDescription && (
//                 <div className="connection-rejected-request">
//                   <span className="connection-rejected-label">요청 사유</span>
//                   <p className="connection-rejected-request-text">
//                     {currentRequestDescription}
//                   </p>
//                 </div>
//               )}
//               <button
//                 type="button"
//                 className="connection-rejected-close"
//                 onClick={handleRejectedModalClose}
//               >
//                 확인
//               </button>
//             </div>
//           </Modal>
//         </>
//       )}

//       {!isAdmin && isMine && (
//         <>
//           <button
//             className="connect-button"
//             onClick={async () => {
//               if (isCheckingInOut) return;

//               try {
//                 setIsCheckingInOut(true);

//                 if (employee.online) {
//                   // 퇴근 처리
//                   await checkOut();
//                   alert("퇴근 처리되었습니다.");
//                 } else {
//                   // 출근 처리
//                   await checkIn();
//                   alert("출근 처리되었습니다.");
//                 }

//                 // 내 정보 새로고침 (작업자가 자신의 정보를 볼 때)
//                 if (fetchMyInfo) {
//                   await fetchMyInfo();
//                 }

//                 // 직원 목록 새로고침 (관리자가 볼 때를 위해)
//                 if (fetchEmployees) {
//                   await fetchEmployees(null);
//                 }
//               } catch (error: any) {
//                 const errorMessage =
//                   error.response?.data?.message ||
//                   error.message ||
//                   "처리 중 오류가 발생했습니다.";
//                 alert(errorMessage);
//               } finally {
//                 setIsCheckingInOut(false);
//               }
//             }}
//             disabled={isCheckingInOut}
//           >
//             {isCheckingInOut ? "처리 중..." : employee.online ? "퇴근" : "출근"}
//           </button>
//         </>
//       )}
//     </div>
//   );
// }

// export default EmployeeDetail;

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
import { getCompanyEquipmentList } from "../../api/equipment";
import { assignEquipment, checkIn, checkOut } from "../../api/user";
import type { Equipment } from "../../types/equipment";

type EmployeeDetailProps = {
  employee: Employee | null;
};

// 모달 타입 통합
type ModalType = "pending" | "rejected" | "timeout" | "requestBox" | null;

function EmployeeDetail({ employee }: EmployeeDetailProps) {
  const { myInfo, fetchEmployees, fetchMyInfo } = useUserStore();
  const { addSentRequest, sentRequests } = useWebRtcRequestStore();
  const isMine = myInfo?.userAccountId === employee?.userAccountId;
  const isAdmin = myInfo?.role === "관리자";

  const { isConnected, connect } = useSSEStore();

  // 모달 상태 하나로 통합
  const [modalType, setModalType] = useState<ModalType>(null);

  // 추가 상태들
  const [currentRequestDescription, setCurrentRequestDescription] =
    useState("");
  const [pendingElapsed, setPendingElapsed] = useState(0);
  const [hasDismissedPending, setHasDismissedPending] = useState(false);
  const pendingStartRef = useRef<number | null>(null);

  // 설비 상태
  const [equipments, setEquipments] = useState<Equipment[]>([]);
  const [selectedEquipmentId, setSelectedEquipmentId] = useState<number | null>(
    null
  );
  const [isEquipmentDropdownOpen, setIsEquipmentDropdownOpen] = useState(false);
  const equipmentDropdownRef = useRef<HTMLDivElement | null>(null);
  const [isAssigning, setIsAssigning] = useState(false);
  const [isCheckingInOut, setIsCheckingInOut] = useState(false);

  // 최근 activeRequest (요청) 계산
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
  const isRejected = activeRequest?.status === "rejected";
  const isTimeout = activeRequest?.status === "timeout";

  // const activeRequestId = activeRequest?.id ?? null;
  const pendingWorkerName =
    activeRequest?.receiverInfo?.name || employee?.name || "";
  const pendingEquipmentName =
    activeRequest?.receiverInfo?.equipmentName || employee?.equipmentName;

  // 모달 오픈 조건 통합 관리
  useEffect(() => {
    if (!isAdmin) {
      setModalType(null);
      return;
    }

    if (isPending && activeRequest) {
      pendingStartRef.current = new Date(activeRequest.requestTime).getTime();
      setCurrentRequestDescription(activeRequest.description ?? "");
      if (!hasDismissedPending) setModalType("pending");
      return;
    }

    if (isRejected && activeRequest) {
      pendingStartRef.current = null;
      setCurrentRequestDescription(activeRequest.description ?? "");
      setModalType("rejected");
      return;
    }

    if (isTimeout && activeRequest) {
      pendingStartRef.current = null;
      setCurrentRequestDescription(activeRequest.description ?? "");
      setModalType("timeout");
      return;
    }

    setModalType(null);
  }, [isAdmin, isPending, isRejected, isTimeout, activeRequest]);

  // pending 시간 카운트
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

  // SSE 연결 보장
  useEffect(() => {
    if (!isConnected) connect();
  }, [isConnected, connect]);

  // 설비 목록 조회
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

  // 설비 지정
  const handleAssignEquipment = async () => {
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
  };

  // 연결 요청
  const handleConnectionRequest = async (description: string) => {
    if (!employee || !isAdmin) return;

    try {
      if (!isConnected) connect();

      const res = await sendConnectionRequest(employee.userAccountId);

      if (!res.success) {
        alert("연결 요청 실패\n\n작업자 SSE 연결 상태 확인 필요");
        return;
      }

      // sentRequests 기록
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

  const handleConnectButtonClick = () => {
    if (modalType === "pending") {
      setModalType("pending");
      return;
    }

    if (modalType === "rejected" || modalType === "timeout") {
      setModalType(modalType);
      return;
    }

    setModalType("requestBox");
  };

  const closePending = () => {
    setHasDismissedPending(true);
    setModalType(null);
  };

  const closeRejected = () => {
    setModalType(null);
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

      {/* --- 기본 정보 --- */}
      <div className="profile-section">
        <img src={"images/default-profile.png"} className="profile-img" />
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

        {/* 관리자일 때만 설비 */}
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
                    onClick={handleAssignEquipment}
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

      {/* ------------------연결 요청 버튼 ------------------- */}
      {isAdmin && (
        <button className="connect-button" onClick={handleConnectButtonClick}>
          {modalType === "pending"
            ? "응답 대기 중..."
            : modalType === "rejected"
            ? "요청이 거절되었습니다"
            : modalType === "timeout"
            ? "요청 시간이 초과되었습니다"
            : "연결 요청"}
        </button>
      )}

      {/* ------------------출근/퇴근 버튼 ------------------- */}
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

      {/* ------------------ 연결 요청 모달------------------- */}
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

      {/* ------------------Pending 모달------------------- */}
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

      {/* ------------------Rejected / Timeout 모달 공용------------------- */}
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
