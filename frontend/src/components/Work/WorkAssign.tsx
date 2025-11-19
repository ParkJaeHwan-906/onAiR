import { useEffect, useMemo, useRef, useState } from "react";
import "../../styles/WorkAssign.css";
import { reAssignTask, getTaskList } from "../../api/task";
import { getUserList } from "../../api/user";
import { useUserStore } from "../../store/useUserStore";
import { useSSEStore } from "../../store/useSSEStore";
import type { Work } from "../../types/work";
import type { Employee } from "../../types/employee";

interface WorkAssignProps {
  onTaskReassigned?: () => void;
}

function WorkAssign({ onTaskReassigned }: WorkAssignProps) {
  const [works, setWorks] = useState<Work[]>([]);
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [selectedWorkId, setSelectedWorkId] = useState<number | null>(null);
  const [isWorkDropdownOpen, setIsWorkDropdownOpen] = useState(false);
  const workDropdownRef = useRef<HTMLDivElement | null>(null);

  const [selectedEmployeeId, setSelectedEmployeeId] = useState<number | null>(
    null
  );
  const [isEmployeeDropdownOpen, setIsEmployeeDropdownOpen] = useState(false);
  const employeeDropdownRef = useRef<HTMLDivElement | null>(null);
  const [loading, setLoading] = useState(false);
  const { myInfo } = useUserStore();
  const { connect: connectSSE } = useSSEStore();

  // 관리자 권한 확인
  const isAdmin = myInfo?.role === "관리자";

  // 작업 목록 조회
  useEffect(() => {
    if (isAdmin) {
      fetchWorks();
      fetchEmployees();
    }
  }, [isAdmin]);

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

  const fetchWorks = async () => {
    try {
      const res = await getTaskList(null, null);
      if (res.success && res.data) {
        // actionStatus가 없으면 action 값으로 변환
        const worksWithStatus = res.data.map((work: Work) => ({
          ...work,
          actionStatus:
            work.actionStatus && work.actionStatus.trim()
              ? work.actionStatus
              : getActionStatus(work.action),
        }));
        setWorks(worksWithStatus);
        // 기본 선택값 없음 - "작업을 선택하세요" 표시
        setSelectedWorkId(null);
      }
    } catch (error) {
      console.error("작업 목록 조회 실패:", error);
    }
  };

  const fetchEmployees = async () => {
    try {
      const res = await getUserList(null);
      if (res.success && res.data) {
        setEmployees(res.data);
        // 기본 선택값 없음 - "담당자를 선택하세요" 표시
        setSelectedEmployeeId(null);
      }
    } catch (error) {
      console.error("직원 목록 조회 실패:", error);
    }
  };

  const selectedWork = useMemo(
    () => works.find((work) => work.id === selectedWorkId) ?? null,
    [works, selectedWorkId]
  );

  const selectedEmployee = useMemo(
    () =>
      employees.find(
        (employee) => employee.userAccountId === selectedEmployeeId
      ) ?? null,
    [employees, selectedEmployeeId]
  );

  useEffect(() => {
    if (!isWorkDropdownOpen && !isEmployeeDropdownOpen) {
      return;
    }

    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as Node;

      if (
        isWorkDropdownOpen &&
        workDropdownRef.current &&
        !workDropdownRef.current.contains(target)
      ) {
        setIsWorkDropdownOpen(false);
      }

      if (
        isEmployeeDropdownOpen &&
        employeeDropdownRef.current &&
        !employeeDropdownRef.current.contains(target)
      ) {
        setIsEmployeeDropdownOpen(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);

    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [isWorkDropdownOpen, isEmployeeDropdownOpen]);

  const handleReAssign = async () => {
    if (!selectedWorkId || !selectedEmployeeId) {
      alert("작업과 담당자를 모두 선택해주세요.");
      return;
    }

    // 선택한 작업과 직원 정보 확인
    const selectedWork = works.find((work) => work.id === selectedWorkId);
    const selectedEmployee = employees.find(
      (emp) => emp.userAccountId === selectedEmployeeId
    );

    if (!selectedWork) {
      alert("선택한 작업 정보를 찾을 수 없습니다. 다시 선택해주세요.");
      return;
    }

    if (!selectedEmployee) {
      alert("선택한 직원 정보를 찾을 수 없습니다. 다시 선택해주세요.");
      return;
    }

    try {
      setLoading(true);
      // console.log("=== 작업 재할당 시작 ===");
      // console.log("재할당 요청 정보:", {
      //   taskId: selectedWorkId,
      //   taskRequest: selectedWork.request,
      //   employeeId: selectedEmployeeId,
      //   employeeName: selectedEmployee.name,
      //   equipmentId: selectedWork.equipmentId,
      //   taskAction: selectedWork.action,
      //   taskUserAccountId: selectedWork.userAccountId,
      // });

      // API 호출 전 유효성 검증
      if (!selectedWorkId || !selectedEmployeeId) {
        throw new Error("작업 ID 또는 담당자 ID가 유효하지 않습니다.");
      }

      if (!selectedWork || !selectedEmployee) {
        throw new Error("작업 또는 담당자 정보를 찾을 수 없습니다.");
      }

      // console.log('재할당할 작업 ID:', selectedWorkId);
      // console.log('재할당할 담당자 ID:', selectedEmployeeId);
      // console.log('재할당할 담당자 이름:', selectedEmployee.name);

      // SSE 연결 상태 확인 및 재연결
      // console.log("🔍 작업 재할당 전 SSE 연결 상태 확인");
      const currentState = useSSEStore.getState();
      const currentEventSource = currentState.eventSource;

      // console.log("📊 현재 SSE 상태:", {
      //   eventSource: !!currentEventSource,
      //   readyState: currentEventSource?.readyState,
      //   isConnected: currentState.isConnected
      // });

      // SSE가 끊겨있거나 연결 중이면 재연결 시도
      if (
        !currentEventSource ||
        currentEventSource.readyState === EventSource.CLOSED ||
        currentEventSource.readyState === EventSource.CONNECTING
      ) {
        // console.log("🔄 SSE 재연결 시도...");
        connectSSE();

        // 재연결 완료 대기 (최대 5초)
        let waitCount = 0;
        while (waitCount < 50) {
          const checkState = useSSEStore.getState();
          const checkEventSource = checkState.eventSource;
          if (
            checkEventSource &&
            checkEventSource.readyState === EventSource.OPEN
          ) {
            // console.log("✅ SSE 연결 완료 - readyState: OPEN");
            break;
          }
          await new Promise((resolve) => setTimeout(resolve, 100));
          waitCount++;
        }

        // 최종 확인
        const finalState = useSSEStore.getState();
        const finalEventSource = finalState.eventSource;
        if (
          !finalEventSource ||
          finalEventSource.readyState !== EventSource.OPEN
        ) {
          // console.error("❌ SSE 연결 실패 - 재할당 시도 중단");
          alert("실시간 연결이 불안정합니다. 잠시 후 다시 시도해주세요.");
          return;
        }
        // console.log("✅ SSE 연결 확인 완료 - 재할당 진행");
      } else if (currentEventSource.readyState === EventSource.OPEN) {
        // console.log("✅ SSE 이미 연결됨 - 재할당 진행");
      }

      const res = await reAssignTask(selectedWorkId, selectedEmployeeId);

      if (res.success) {
        alert("작업이 재할당되었습니다.");
        // 작업 목록 새로고침
        await fetchWorks();
        // WorkBig 목록 새로고침
        if (onTaskReassigned) {
          onTaskReassigned();
        }
        // 선택 초기화
        setSelectedWorkId(null);
        setSelectedEmployeeId(null);
      } else {
        // console.error("재할당 실패 - 응답:", res);
        alert(res.message || "작업 재할당에 실패했습니다.");
      }
    } catch (error: any) {
      // 백엔드 에러 메시지 추출 (여러 가능성 체크)
      const errorMessage =
        error.response?.data?.message ||
        error.response?.data?.error ||
        error.response?.data?.data?.message ||
        error.response?.data?.data?.error ||
        (typeof error.response?.data === "string"
          ? error.response.data
          : null) ||
        error.message ||
        "알 수 없는 오류";

      // console.error('추출된 에러 메시지:', errorMessage);

      // 에러 상태 코드별 메시지
      if (error.response?.status === 500) {
        // // 500 에러 시 실제 재할당 여부 확인
        // console.log('=== 500 에러 발생 - 작업 재할당 여부 확인 시작 ===');
        // console.log('확인할 작업 ID:', selectedWorkId);
        // console.log('확인할 담당자 ID:', selectedEmployeeId);

        try {
          // 잠시 대기 후 작업 목록 재조회
          await new Promise((resolve) => setTimeout(resolve, 500));
          // console.log('작업 목록 재조회 중...');
          const verifyRes = await getTaskList(null, null);
          // console.log('작업 목록 재조회 결과:', {
          //   success: verifyRes.success,
          //   dataLength: verifyRes.data?.length || 0
          // });

          const reassignedTask = verifyRes.data?.find(
            (t: Work) => t.id === selectedWorkId
          );
          // console.log('재할당 확인 결과:', {
          //   taskFound: !!reassignedTask,
          //   taskId: reassignedTask?.id,
          //   assignedUserAccountId: reassignedTask?.userAccountId,
          //   expectedUserAccountId: selectedEmployeeId,
          //   isMatch: reassignedTask?.userAccountId === selectedEmployeeId,
          //   taskAction: reassignedTask?.action
          // });

          if (
            reassignedTask &&
            reassignedTask.userAccountId === selectedEmployeeId
          ) {
            // 실제로는 재할당되었음
            // console.log('✅ 실제로 재할당되었음 - 성공 처리');
            alert(
              "작업이 재할당되었습니다.\n\n(서버 오류가 발생했지만 작업 재할당은 완료되었습니다. 페이지를 새로고침해주세요.)"
            );
            await fetchWorks();
            if (onTaskReassigned) {
              onTaskReassigned();
            }
            setSelectedWorkId(null);
            setSelectedEmployeeId(null);
          } else {
            // console.log('❌ 실제로 재할당되지 않음 - 실패 처리');
            // console.log('재할당된 작업 정보:', reassignedTask);
            alert(
              `작업 재할당에 실패했습니다.\n\n서버 내부 오류가 발생했습니다.\n\n에러: ${errorMessage}\n\n작업 ID: ${selectedWorkId}\n담당자 ID: ${selectedEmployeeId}\n\n백엔드 로그를 확인해주세요.\n\n(SSE 연결이 끊어져 있을 수 있습니다. 페이지를 새로고침해주세요.)`
            );
          }
        } catch (verifyError) {
          // console.error('재할당 확인 중 오류:', verifyError);
          alert(
            `작업 재할당에 실패했습니다.\n\n서버 내부 오류가 발생했습니다.\n\n에러: ${errorMessage}\n\n작업 ID: ${selectedWorkId}\n담당자 ID: ${selectedEmployeeId}\n\n(재할당 확인 중 오류가 발생했습니다.)`
          );
        }
      } else if (error.response?.status === 400) {
        // SSE 전송 실패인 경우 특별 처리
        if (
          errorMessage.includes("SSE 전송에 실패했습니다") ||
          errorMessage.includes("SSE")
        ) {
          alert(
            `작업 재할당 시도 중 실시간 알림 전송에 실패했습니다.\n\n실제 작업 재할당이 완료되었는지 확인해주세요.\n페이지를 새로고침하여 작업 목록을 확인해주세요.\n\n에러: ${errorMessage}`
          );
          // 작업 목록 새로고침을 시도
          await fetchWorks();
          if (onTaskReassigned) {
            onTaskReassigned();
          }
        } else {
          alert(
            `작업 재할당에 실패했습니다.\n\n잘못된 요청입니다.\n\n에러: ${errorMessage}`
          );
        }
      } else if (error.response?.status === 401) {
        alert(
          `작업 재할당에 실패했습니다.\n\n인증이 필요합니다. 다시 로그인해주세요.`
        );
      } else if (error.response?.status === 403) {
        alert(`작업 재할당에 실패했습니다.\n\n권한이 없습니다.`);
      } else {
        alert(`작업 재할당에 실패했습니다.\n\n에러: ${errorMessage}`);
      }
    } finally {
      setLoading(false);
    }
  };

  if (!isAdmin) {
    return null; // 관리자가 아니면 작업 재할당 컴포넌트를 표시하지 않음
  }

  const isBodyScrollable = isWorkDropdownOpen || isEmployeeDropdownOpen;

  return (
    <div className="work-assign">
      <div className="work-assign-header">작업 재할당</div>

      <div
        className={`work-assign-body${isBodyScrollable ? " scrollable" : ""}`}
      >
        <div className="assign-header">작업</div>
        <div className="work-select-wrapper" ref={workDropdownRef}>
          <button
            type="button"
            className={`work-select-trigger${
              isWorkDropdownOpen ? " open" : ""
            }`}
            onClick={() => setIsWorkDropdownOpen((prev) => !prev)}
          >
            <span>
              {selectedWork ? selectedWork.request : "작업을 선택하세요"}
            </span>
          </button>
          {isWorkDropdownOpen && (
            <ul className="work-select-dropdown">
              {works.length === 0 ? (
                <li className="empty-option">작업이 없습니다.</li>
              ) : (
                works.map((work) => (
                  <li key={work.id}>
                    <button
                      type="button"
                      className={`work-select-option${
                        work.id === selectedWorkId ? " selected" : ""
                      }`}
                      onClick={() => {
                        setSelectedWorkId(work.id);
                        setIsWorkDropdownOpen(false);
                      }}
                    >
                      <span className="work-select-option-title">
                        {work.request}
                      </span>
                      <span className="work-select-option-meta">
                        {work.equipmentName}
                      </span>
                    </button>
                  </li>
                ))
              )}
            </ul>
          )}
        </div>

        <div className="assign-header">담당자</div>
        <div className="work-select-wrapper" ref={employeeDropdownRef}>
          <button
            type="button"
            className={`work-select-trigger${
              isEmployeeDropdownOpen ? " open" : ""
            }`}
            onClick={() => setIsEmployeeDropdownOpen((prev) => !prev)}
          >
            {selectedEmployee
              ? `${selectedEmployee.name} (${selectedEmployee.part})`
              : "담당자를 선택하세요"}
          </button>
          {isEmployeeDropdownOpen && (
            <ul className="work-select-dropdown">
              {employees.length === 0 ? (
                <li className="empty-option">직원이 없습니다.</li>
              ) : (
                employees.map((employee) => (
                  <li key={employee.userAccountId}>
                    <button
                      type="button"
                      className={`work-select-option${
                        employee.userAccountId === selectedEmployeeId
                          ? " selected"
                          : ""
                      }`}
                      onClick={() => {
                        setSelectedEmployeeId(employee.userAccountId);
                        setIsEmployeeDropdownOpen(false);
                      }}
                    >
                      <span className="work-select-option-title">
                        {employee.name}
                      </span>
                      <span className="work-select-option-meta">
                        {employee.part} |{" "}
                        {employee.online ? "온라인" : "오프라인"}
                      </span>
                    </button>
                  </li>
                ))
              )}
            </ul>
          )}
        </div>
      </div>

      <button
        className="assign-button"
        onClick={handleReAssign}
        disabled={loading || !selectedWorkId || !selectedEmployeeId}
      >
        {loading ? "재할당 중..." : "작업 재할당"}
      </button>
    </div>
  );
}

export default WorkAssign;
