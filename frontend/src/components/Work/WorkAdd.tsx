import { useState, useEffect, useRef } from "react";
import "../../styles/WorkAdd.css";
import { registTask, getTaskList, assignTaskToWorker } from "../../api/task";
import { getCompanyEquipmentList } from "../../api/equipment";
import { getUserList } from "../../api/user";
import { useUserStore } from "../../store/useUserStore";
import { useSSEStore } from "../../store/useSSEStore";
import type { Employee } from "../../types/employee";
import type { Work } from "../../types/work";

interface Equipment {
  id: number;
  category: string;
  name: string;
}

interface WorkAddProps {
  title?: string; // 상단 제목 (기본값: '작업 추가')
  label?: string; // textarea 라벨 (기본값: '작업 내용')
  placeholder?: string; // placeholder 텍스트
  buttonText?: string; // 버튼 텍스트
  onTaskAdded?: () => void; // 작업 등록 성공 후 콜백
  onSubmit?: (text: string) => void; // 커스텀 제출 핸들러 (연결 요청 등)
}

function WorkAdd({
  title = "작업 추가",
  label = "작업 내용",
  placeholder = "작업 내용을 입력하세요",
  buttonText = "작업 등록",
  onTaskAdded,
  onSubmit,
}: WorkAddProps) {
  const [text, setText] = useState("");
  const [equipments, setEquipments] = useState<Equipment[]>([]);
  const [selectedEquipmentId, setSelectedEquipmentId] = useState<number | null>(
    null
  );
  const [isEquipmentDropdownOpen, setIsEquipmentDropdownOpen] = useState(false);
  const equipmentDropdownRef = useRef<HTMLDivElement | null>(null);

  const [employees, setEmployees] = useState<Employee[]>([]);
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

  useEffect(() => {
    if (isAdmin) {
      fetchEquipments();
      fetchEmployees();
    }
  }, [isAdmin]);

  useEffect(() => {
    if (!isEquipmentDropdownOpen && !isEmployeeDropdownOpen) {
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
  }, [isEquipmentDropdownOpen, isEmployeeDropdownOpen]);

  const fetchEquipments = async () => {
    try {
      const res = await getCompanyEquipmentList();
      if (res.success && res.data) {
        setEquipments(res.data);
        // 기본 선택값 없음 - "설비를 선택하세요" 표시
        setSelectedEquipmentId(null);
      }
    } catch (error) {
      console.error("장비 목록 조회 실패:", error);
    }
  };

  const fetchEmployees = async () => {
    try {
      const res = await getUserList(null);
      if (res.success && res.data) {
        setEmployees(res.data);
      }
    } catch (error) {
      console.error("직원 목록 조회 실패:", error);
    }
  };

  // 모든 직원을 표시하되, 해당 장비 담당자를 우선 표시
  const filteredEmployees = selectedEquipmentId
    ? [...employees].sort((a: Employee, b: Employee) => {
        // 해당 장비 담당자를 우선 표시
        const aIsAssigned = a.equipmentId === selectedEquipmentId ? 1 : 0;
        const bIsAssigned = b.equipmentId === selectedEquipmentId ? 1 : 0;
        return bIsAssigned - aIsAssigned;
      })
    : employees;

  const handleClick = async () => {
    if (!text.trim()) {
      alert("내용을 입력해주세요.");
      return;
    }

    // onSubmit이 있으면 커스텀 핸들러 실행 (연결 요청 등)
    if (onSubmit) {
      onSubmit(text.trim());
      setText("");
      return;
    }

    if (isAdmin && !selectedEquipmentId) {
      alert("장비를 선택해주세요.");
      return;
    }

    if (isAdmin && !selectedEmployeeId) {
      alert("담당자를 선택해주세요.");
      return;
    }

    // 관리자인 경우: 등록 전에 담당자 검증
    if (isAdmin && selectedEmployeeId) {
      // 최신 직원 정보 가져오기
      try {
        const employeeRes = await getUserList(null);
        if (employeeRes.success && employeeRes.data) {
          const selectedEmployee = employeeRes.data.find(
            (emp: Employee) => emp.userAccountId === selectedEmployeeId
          );

          if (!selectedEmployee) {
            alert("담당자 정보를 찾을 수 없습니다. 페이지를 새로고침해주세요.");
            return;
          }

          // 설비 미지정 검증
          if (!selectedEmployee.equipmentId) {
            alert("⚠️ 작업 등록 불가\n\n작업자에게 설비가 지정되지 않았습니다.\n직원 관리 페이지에서 설비를 지정해주세요.");
            return;
          }
          
          // 오프라인 상태 검증
          if (!selectedEmployee.online) {
            alert("⚠️ 작업 등록 불가\n\n작업자가 오프라인 상태입니다.\n작업자가 로그인한 후 다시 시도해주세요.");
            return;
          }
        } else {
          alert("직원 정보를 불러올 수 없습니다. 다시 시도해주세요.");
          return;
        }
      } catch (error) {
        alert("직원 정보 조회 중 오류가 발생했습니다. 다시 시도해주세요.");
        return;
      }
    }

    try {
      setLoading(true);
      const equipmentId = isAdmin ? selectedEquipmentId! : myInfo?.equipmentId;

      if (!equipmentId) {
        alert("장비 정보가 없습니다.");
        return;
      }

      const requestText = text.trim();

      // 작업 등록
      const res = await registTask(equipmentId, requestText);

      if (!res.success) {
        alert(res.message || "작업 등록에 실패했습니다.");
        return;
      }

      // 3. 담당자에게 바로 할당 (관리자인 경우)
      if (isAdmin && selectedEmployeeId) {
        try {
          // SSE 연결 확인 및 재연결
          console.log("🔍 작업 할당 전 SSE 연결 상태 확인");
          const currentState = useSSEStore.getState();
          const currentEventSource = currentState.eventSource;
          
          console.log("📊 현재 SSE 상태:", {
            eventSource: !!currentEventSource,
            readyState: currentEventSource?.readyState,
            isConnected: currentState.isConnected
          });
          
          // SSE 연결이 없거나 끊어진 경우 재연결
          if (
            !currentEventSource ||
            currentEventSource.readyState === EventSource.CLOSED ||
            currentEventSource.readyState === EventSource.CONNECTING
          ) {
            console.log("🔄 SSE 재연결 시도...");
            connectSSE();
            
            // 재연결 완료 대기 (최대 5초)
            let waitCount = 0;
            while (waitCount < 50) {
              const checkState = useSSEStore.getState();
              const checkEventSource = checkState.eventSource;
              if (checkEventSource && checkEventSource.readyState === EventSource.OPEN) {
                console.log("✅ SSE 연결 완료 - readyState: OPEN");
                break;
              }
              await new Promise(resolve => setTimeout(resolve, 100));
              waitCount++;
            }
            
            // 최종 확인
            const finalState = useSSEStore.getState();
            const finalEventSource = finalState.eventSource;
            if (!finalEventSource || finalEventSource.readyState !== EventSource.OPEN) {
              console.error("❌ SSE 연결 실패 - 할당 시도 중단");
              alert("⚠️ 실시간 연결이 불안정합니다. 잠시 후 다시 시도해주세요.");
              return;
            }
            console.log("✅ SSE 연결 확인 완료 - 할당 진행");
          } else if (currentEventSource.readyState === EventSource.OPEN) {
            console.log("✅ SSE 이미 연결됨 - 할당 진행");
          }

          // 작업 등록 후 트랜잭션 커밋 대기
          await new Promise((resolve) => setTimeout(resolve, 1000));

          // 등록된 작업 찾기
          const taskListRes = await getTaskList(equipmentId, null);

          if (
            taskListRes.success &&
            taskListRes.data &&
            taskListRes.data.length > 0
          ) {
            // 같은 요청 내용과 장비 ID를 가진 작업 찾기
            const matchingTasks = taskListRes.data.filter((task: Work) => {
              return task.request === requestText && task.equipmentId === equipmentId;
            });

            if (matchingTasks.length > 0) {
              // 가장 최근에 등록된 작업 (lastUpdateTime 기준 내림차순)
              const latestTask = matchingTasks.sort(
                (a: Work, b: Work) =>
                  new Date(b.lastUpdateTime).getTime() -
                  new Date(a.lastUpdateTime).getTime()
              )[0];

              // 담당자 정보 찾기 (이미 검증했지만 다시 확인)
              const selectedEmployee = employees.find(
                (emp) => emp.userAccountId === selectedEmployeeId
              );

              if (!selectedEmployee) {
                alert(
                  "작업은 등록되었지만 담당자 정보를 찾을 수 없어 할당에 실패했습니다."
                );
                return;
              }

              // 유효성 검증
              if (!latestTask.id || !selectedEmployeeId) {
                alert("작업 ID 또는 담당자 ID가 유효하지 않습니다.");
                return;
              }

              // 작업 할당 API 호출
              try {
                const assignRes = await assignTaskToWorker(
                  latestTask.id,
                  selectedEmployeeId
                );

                if (assignRes.success) {
                  alert("작업이 등록되고 담당자에게 할당되었습니다.");
                  if (onTaskAdded) {
                    onTaskAdded();
                  }
                } else {
                  alert("작업은 등록되었지만 할당에 실패했습니다: " + (assignRes.message || "알 수 없는 오류"));
                }
              } catch (error: any) {
                const errorMessage =
                  error.response?.data?.message ||
                  error.message ||
                  "알 수 없는 오류";

                console.error("❌ 작업 할당 API 호출 실패:", error);
                console.error("에러 상태:", error.response?.status);
                console.error("에러 메시지:", errorMessage);

                // 500 에러 시 실제 할당 여부 확인
                if (error.response?.status === 500) {
                  console.log("🔍 500 에러 발생 - 실제 할당 여부 확인 중...");
                  await new Promise((resolve) => setTimeout(resolve, 1000));
                  
                  const verifyRes = await getTaskList(equipmentId, null);
                  console.log("📋 작업 목록 확인 결과:", verifyRes);
                  
                  const assignedTask = verifyRes.data?.find(
                    (t: Work) => t.id === latestTask.id
                  );
                  
                  console.log("🔍 찾은 작업:", assignedTask);
                  console.log("🔍 할당된 담당자 ID:", assignedTask?.userAccountId);
                  console.log("🔍 예상 담당자 ID:", selectedEmployeeId);

                  if (
                    assignedTask &&
                    assignedTask.userAccountId === selectedEmployeeId
                  ) {
                    console.log("✅ 실제로 할당됨 - 롤백되지 않음");
                    alert(
                      "작업이 등록되고 담당자에게 할당되었습니다.\n\n(서버 오류가 발생했지만 작업 할당은 완료되었습니다. 페이지를 새로고침해주세요.)"
                    );
                    if (onTaskAdded) {
                      onTaskAdded();
                    }
                  } else {
                    console.error("❌ 실제로 할당되지 않음 - 롤백됨");
                    console.error("⚠️ 백엔드에서 SSE 전송 실패로 인한 트랜잭션 롤백");
                    console.error("백엔드 로그에서 다음을 확인하세요:");
                    console.error("1. SseManager.taskAssign() - emitter 찾기 실패");
                    console.error("2. SSE 전송 IOException");
                    alert(
                      `⚠️ 작업 할당 실패\n\n서버 내부 오류가 발생했습니다.\n\n가능한 원인:\n- 백엔드에서 SSE 연결을 찾지 못함\n- SSE 전송 실패로 인한 트랜잭션 롤백\n\n백엔드 로그를 확인해주세요.\n\n에러: ${errorMessage}`
                    );
                  }
                } else {
                  alert(
                    `작업은 등록되었지만 할당에 실패했습니다.\n\n에러: ${errorMessage}`
                  );
                }
              }
            } else {
              alert(
                "작업이 등록되었지만 할당에 실패했습니다. 작업 목록을 새로고침해주세요."
              );
            }
          } else {
            alert("작업이 등록되었습니다.");
          }
        } catch (assignError: any) {
          const errorMessage =
            assignError.response?.data?.message ||
            assignError.message ||
            "알 수 없는 오류";
          alert(
            `작업은 등록되었지만 할당에 실패했습니다.\n\n에러: ${errorMessage}`
          );
        }
      } else {
        alert("작업이 등록되었습니다.");
      }

    setText("");
      setSelectedEmployeeId(null);
      if (onTaskAdded) {
        onTaskAdded();
      }
    } catch (error: any) {
      console.error("작업 등록 실패:", error);
      alert(error.response?.data?.message || "작업 등록에 실패했습니다.");
    } finally {
      setLoading(false);
    }
  };

  if (!isAdmin) {
    return null; // 관리자가 아니면 작업 추가 컴포넌트를 표시하지 않음
  }

  const selectedEquipment = equipments.find(
    (eq) => eq.id === selectedEquipmentId
  );
  const selectedEmployee = employees.find(
    (emp) => emp.userAccountId === selectedEmployeeId
  );

  // 장비 변경 시 담당자 선택 초기화
  const handleEquipmentChange = (equipmentId: number) => {
    setSelectedEquipmentId(equipmentId);
    setSelectedEmployeeId(null); // 장비 변경 시 담당자 선택 초기화
    setIsEquipmentDropdownOpen(false);
  };

  return (
    <div className="work-add">
      <div className="work-add-header">{title}</div>

      {!onSubmit && (
        <>
          <div className="assign-header">설비</div>
          <div className="work-select-wrapper" ref={equipmentDropdownRef}>
            <button
              type="button"
              className={`work-select-trigger${
                isEquipmentDropdownOpen ? " open" : ""
              }`}
              onClick={() => setIsEquipmentDropdownOpen((prev) => !prev)}
            >
              {selectedEquipment
                ? `${selectedEquipment.name} (${selectedEquipment.category})`
                : "설비를 선택하세요"}
            </button>
            {isEquipmentDropdownOpen && (
              <ul className="work-select-dropdown">
                {equipments.map((equipment) => (
                  <li key={equipment.id}>
                    <button
                      type="button"
                      className={`work-select-option${
                        equipment.id === selectedEquipmentId ? " selected" : ""
                      }`}
                      onClick={() => handleEquipmentChange(equipment.id)}
                    >
                      <span className="work-select-option-title">
                        {equipment.name}
                      </span>
                      <span className="work-select-option-meta">
                        {equipment.category}
                      </span>
                    </button>
                  </li>
                ))}
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
              disabled={!selectedEquipmentId}
            >
              {selectedEmployee
                ? `${selectedEmployee.name} (${selectedEmployee.part})`
                : "담당자를 선택하세요"}
            </button>
            {isEmployeeDropdownOpen && selectedEquipmentId && (
              <ul className="work-select-dropdown">
                {filteredEmployees.length === 0 ? (
                  <li
                    style={{
                      padding: "10px",
                      textAlign: "center",
                      color: "#9CA3AF",
                    }}
                  >
                    직원이 없습니다.
                  </li>
                ) : (
                  filteredEmployees.map((employee) => (
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
                          {employee.part}
                          {/* {employee.equipmentId === selectedEquipmentId ? ' · 담당' : employee.equipmentId ? ' · 다른 장비 담당' : ' · 미할당'} */}
                          {" · "}
                          {employee.online ? "온라인" : "오프라인"}
                        </span>
                      </button>
                    </li>
                  ))
                )}
              </ul>
            )}
          </div>
        </>
      )}

      <div className="request-header">{label}</div>
      <textarea
        className="request-body"
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder={placeholder}
      ></textarea>
      <button
        className="add-button"
        onClick={handleClick}
        disabled={
          loading || (!onSubmit && (!selectedEquipmentId || !selectedEmployeeId)) || !text.trim()
        }
      >
        {loading ? "등록 중..." : buttonText}
      </button>
    </div>
  );
}

export default WorkAdd;
